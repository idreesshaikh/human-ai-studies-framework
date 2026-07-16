from csv import Error
from os import dup, error
from typing import Literal, TypeVar, Any

import numpy as np
import pandas as pd
import torch
from error_types import ErrorTypes
from pydantic import BaseModel, ValidationError, create_model
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModel, AutoTokenizer
import tqdm
from semhash import SemHash
from pydantic import BaseModel, TypeAdapter, Field
from pathlib import Path

T = TypeVar("T")

COL_ALL = -1


def flag_with_priority(
    mask: pd.DataFrame, error_type: int, row: int, col: int | str
) -> None:
    # col -1 means all

    priority_list = [
        0,
        ErrorTypes.INCORRECT_VALUES.value,
        ErrorTypes.MISFIELDED_VALUES.value,
        ErrorTypes.FUZZY_DUPLICATES.value,
        ErrorTypes.EXACT_DUPLICATES.value,
        ErrorTypes.MISFIELDED_VALUES_IN_ANY_CASE.value,  # hack for highest prio because flagging prio is broken
    ]

    new_prio = priority_list.index(error_type)
    if col != COL_ALL and isinstance(col, str):
        col = mask.columns.get_loc(col)

    if col == COL_ALL:
        current_prio = priority_list.index(mask.iloc[row, 0])
    else:
        current_prio = priority_list.index(mask.iloc[row, col])

    if current_prio < new_prio:
        if col == COL_ALL:
            mask.iloc[row, :] = error_type
        else:
            mask.iloc[row, col] = error_type


def apply(
    input_df_path: Path,
    pollution_functions: list["Detect"],
    output_df_path: Path,
):
    df = pd.read_csv(input_df_path)
    total_cells = df.shape[0] * df.shape[1]
    mask = pd.DataFrame(0, index=df.index, columns=df.columns)
    detected = 0
    for pollution_cls in pollution_functions:
        detected += pollution_cls.detect(df, mask)
        print(
            f"Detected {pollution_cls.__name__} {round(detected / total_cells * 100, 3)}%"
        )

    mask = mask.replace(
        ErrorTypes.MISFIELDED_VALUES_IN_ANY_CASE.value,
        ErrorTypes.MISFIELDED_VALUES.value,
    )
    mask.to_csv(output_df_path, index=False)


class Detect:
    error_type: ErrorTypes
    col: str

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int: ...


class DetectDuplicates(Detect):
    error_type = ErrorTypes.EXACT_DUPLICATES

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0
        for idx, is_duplicate in enumerate(input.duplicated(keep=False)):
            if not is_duplicate:
                continue

            flag_with_priority(mask, cls.error_type.value, idx, COL_ALL)
            detected += input.shape[1]

        return detected


class DetectTooLongString(Detect):
    error_type = ErrorTypes.MISFIELDED_VALUES_IN_ANY_CASE
    str_len = 128

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0
        for idx, row in input.iterrows():
            for col in input.columns:
                value = row[col]
                if isinstance(value, str) and len(value) > cls.str_len and "," in value:
                    flag_with_priority(mask, cls.error_type.value, idx, col)
                    detected += 1
        return detected


class DetectIncorrectValues(Detect):
    error_type = ErrorTypes.INCORRECT_VALUES
    pydantic_class: BaseModel

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0
        for idx, row in input.iterrows():
            try:
                cls.pydantic_class.model_validate(row.to_dict())
            except ValidationError as e:
                cols = [
                    d["loc"][0]
                    for d in e.errors(
                        include_context=False, include_input=False, include_url=False
                    )
                ]
                for col in cols:
                    flag_with_priority(mask, cls.error_type.value, idx, col)
                    detected += 1
                    # print(col, input.loc[idx, col])
        return detected


class DetectIncorrectFuzzyValues(Detect):
    error_type = ErrorTypes.FUZZY_DUPLICATES
    pydantic_class: BaseModel
    string_fields: list[str]

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0

        # string_fields = []
        # for field_name, field_info in cls.pydantic_class.model_fields.items():
        #     if field_info.annotation == str or str in getattr(field_info.annotation, '__args__', []):
        #         string_fields.append(field_name)

        for field in cls.string_fields:
            dataframe = input[field].to_list()
            exact = input[field].duplicated()
            dataframe = [
                str(val)
                for idx, val in input[field].items()
                if not exact[idx] and mask[field][idx] == 0
            ]
            # print(dataframe)
            semhash = SemHash.from_records(records=dataframe, columns=[field])
            duplicates = semhash.self_deduplicate(threshold=0.9).duplicates

            for duplicate in duplicates:
                # print(f"Duplicates of {duplicate.record}: {duplicate.duplicates}")
                matches = input[input[field] == duplicate.record].index
                for idx in matches:
                    flag_with_priority(mask, cls.error_type.value, idx, field)
                    detected += 1

        return detected


class UniquenessFuzzyDuplicates(Detect):
    error_type = ErrorTypes.FUZZY_DUPLICATES
    unique_together_cols: list[str] = []

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0
        for idx, is_duplicate in enumerate(
            input.duplicated(subset=cls.unique_together_cols, keep=False)
        ):
            if not is_duplicate:
                continue

            flag_with_priority(mask, cls.error_type.value, idx, COL_ALL)
            detected += input.shape[1]

        return detected


# class DetectFuzzyDuplicates(Detect):
#     error_type = ErrorTypes.FUZZY_DUPLICATES
#     model = None
#     tokenizer = None
#     threshold: float = 0.85
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#     @classmethod
#     def _get_embeddings(cls, texts: list[str], batch_size: int = 1) -> np.ndarray:
#         embeddings_list = []
#         for i in tqdm.tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
#             batch_texts = texts[i : i + batch_size]
#             inputs = cls.tokenizer(
#                 batch_texts, return_tensors="pt", truncation=True, padding=True
#             )
#             inputs = {k: v.to(cls.device) for k, v in inputs.items()}
#             with torch.no_grad():
#                 outputs = cls.model(**inputs)
#             batch_embeddings = outputs.last_hidden_state.mean(dim=1)
#             embeddings_list.append(batch_embeddings.cpu().numpy())
#         return np.vstack(embeddings_list)

#     @classmethod
#     def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
#         model_name = "sentence-transformers/all-mpnet-base-v2"
#         cls.model = AutoModel.from_pretrained(model_name).to(cls.device)
#         cls.tokenizer = AutoTokenizer.from_pretrained(model_name)

#         if cls.model is None or cls.tokenizer is None:
#             raise ValueError("Model and tokenizer must be set before detection.")

#         detected = 0

#         combined = input.astype(str).agg(" ".join, axis=1).tolist()
#         embeddings = cls._get_embeddings(combined)
#         similarity_matrix = cosine_similarity(embeddings)

#         for i in range(len(input)):
#             for j in range(i + 1, len(input)):
#                 if similarity_matrix[i, j] > cls.threshold:
#                     # print(f"Similar rows (index {i}, {j}):")
#                     # print(input.iloc[[i, j]])
#                     flag_with_priority(mask, cls.error_type.value, i, COL_ALL)
#                     flag_with_priority(mask, cls.error_type.value, j, COL_ALL)
#                     detected += input.shape[1] * 2
#         return detected


class DetectFuzzyDuplicates(Detect):
    error_type = ErrorTypes.INCORRECT_VALUES
    pydantic_class: BaseModel

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        detected = 0

        # input = input.head(1000)

        string_fields = [
            field
            for field, ftype in cls.pydantic_class.model_fields.items()
            if hasattr(ftype.annotation, "__origin__")
            and ftype.annotation.__origin__ in (Literal, str)
        ]

        # print(input.to_dict(orient='records'))
        records = (
            input.reset_index()
            .rename(columns={"index": "row_id"})
            .to_dict(orient="records")
        )
        # print(records)
        semhash = SemHash.from_records(records=records, columns=string_fields)
        duplicates = semhash.self_deduplicate(threshold=0.9).duplicates

        for duplicate in duplicates:
            # print(duplicate.record)
            # print(f"Duplicates of {duplicate.record}: {duplicate.duplicates}")
            if duplicate.exact:
                continue

            flag_with_priority(
                mask, cls.error_type.value, duplicate.record["row_id"], COL_ALL
            )
            detected += 1
        return detected


class DetectMisfieldedValues(Detect):
    error_type = ErrorTypes.MISFIELDED_VALUES
    pydantic_class: BaseModel
    skip_types = {
        ErrorTypes.EXACT_DUPLICATES.value,
        ErrorTypes.FUZZY_DUPLICATES.value,
        ErrorTypes.MISFIELDED_VALUES_IN_ANY_CASE.value,
    }

    @classmethod
    def validate_value(cls, field_name: str, value) -> bool:
        try:
            cls.pydantic_class.__pydantic_validator__.validate_assignment(
                cls.pydantic_class.model_construct(), field_name, value
            )  # https://github.com/pydantic/pydantic/discussions/7367#discussioncomment-6953794
            return True
        except Exception as e:
            return False

    @classmethod
    def get_field_type(cls, field: str) -> Any:
        return cls.pydantic_class.model_fields[field]

    @classmethod
    def detect(cls, input: pd.DataFrame, mask: pd.DataFrame) -> int:
        # print(cls.pydantic_class.model_fields)
        detected = 0
        for idx, row in input.iterrows():
            for col in input.columns:
                col_idx = mask.columns.get_loc(col)
                col_value = row[col]
                if (
                    not cls.validate_value(col, col_value)
                    and mask.iloc[idx, col_idx] not in cls.skip_types
                ):
                    for other_col in input.columns:
                        if other_col == col:
                            continue  # ignore the same col
                        other_col_idx = mask.columns.get_loc(other_col)
                        if mask.iloc[idx, other_col_idx] in cls.skip_types:
                            continue  # ignore if already higher prio

                        other_col_value = row[other_col]
                        if not cls.validate_value(other_col, other_col_value):
                            if (
                                cls.validate_value(other_col, col_value)
                                and cls.validate_value(col, other_col_value)
                            ):  # we found a swap, its greedy, but there is no way to figure out which fitting cols its from
                                # print(
                                #     f"SWAP: Detected misfielded value in row {idx}, column {col}: {col_value} and {other_col}: {other_col_value} are swapped"
                                # )
                                flag_with_priority(
                                    mask, cls.error_type.value, idx, col_idx
                                )
                                flag_with_priority(
                                    mask, cls.error_type.value, idx, other_col_idx
                                )
                                detected += 2
                                continue

                        col_type = cls.get_field_type(col.replace("-", "_"))
                        other_col_type = cls.get_field_type(other_col.replace("-", "_"))
                        if (
                            col_type.annotation == other_col_type.annotation
                            and col_type.metadata == other_col_type.metadata
                        ):
                            # print(
                            #     f"col_type {col_type} and other_col_type {other_col_type} are equal"
                            # )
                            continue  # if both are literals, ints floats with the same allowed values, we cannot do anything here

                        if col_value == other_col_value and cls.validate_value(
                            other_col, other_col_value
                        ):
                            # print(
                            #     f"MOVE: Detected misfielded value in row {idx}, column {col}: {col_value} and {other_col}: {other_col_value} are moved"
                            # )
                            flag_with_priority(mask, cls.error_type.value, idx, col_idx)
                            # flag_with_priority(
                            #     mask, cls.error_type.value, idx, other_col_idx
                            # )
                            detected += 1
                            continue

                        # if cls.validate_value(other_col, other_col_value):
                        #     print(
                        #         f"SIMPLE MOVE: Detected misfielded value in row {idx}, column {col}: {col_value} and {other_col}: {other_col_value} are moved"
                        #     )
                        #     flag_with_priority(mask, cls.error_type.value, idx, col_idx)
                        #     flag_with_priority(
                        #         mask, cls.error_type.value, idx, other_col_idx
                        #     )
                        #     detected += 1
                        #     continue

        return detected
