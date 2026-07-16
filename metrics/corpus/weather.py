import pandas as pd
from pathlib import Path
from error_types import ErrorTypes
from pollute import (
    Pollute,
    create_pollution_mask,
    PolluteCellWithProb,
    PolluteReformatAll,
)
import numpy as np
from copy import deepcopy
import random
import datetime


class CToF(Pollute):
    error_type: ErrorTypes = ErrorTypes.HETROGENEOUS_FORMATTING
    col: str = "Temp3pm"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        input[cls.col] = input[cls.col].apply(lambda x: round(x * 1.8 + 32, 1))
        return len(input.index)


class DirToDegree(PolluteReformatAll):
    error_type: ErrorTypes = ErrorTypes.HETROGENEOUS_FORMATTING
    col: str = "WindGustDir"

    letter_dir_to_degree: list[str] = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    @classmethod
    def cell_reformat_callback(cls, x):
        return cls.letter_dir_to_degree.index(x) * 22.5


class GaussBase(Pollute):
    """Borrowed from https://stackoverflow.com/questions/46093073/adding-gaussian-noise-to-a-dataset-of-floating-points-and-save-it-python"""

    error_type: ErrorTypes = ErrorTypes.GAUSSIAN_NOISE

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        mu, sigma = 0, 0.1
        noise = np.random.normal(mu, sigma, [len(input.index)])
        noise = np.round(noise, 1)
        input[cls.col] = round(input[cls.col] + noise, 1)
        return len(input.index)


class GaussWindSpeed(GaussBase):
    col: str = "WindGustSpeed"


class GaussCairns(Pollute):
    """Borrowed from https://stackoverflow.com/questions/46093073/adding-gaussian-noise-to-a-dataset-of-floating-points-and-save-it-python"""

    error_type: ErrorTypes = ErrorTypes.GAUSSIAN_NOISE
    col = "Humidity9am"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        mod = 0
        mu = 0
        sigma = 0.1
        for idx, row in input.iterrows():
            date = datetime.datetime.strptime(row["Date"], "%Y-%m-%d")
            location = row["Location"]
            if date.month in {5, 6, 7, 8, 9} and location == "Cairns":
                input.loc[idx, cls.col] += round(random.gauss(mu, sigma), 1)
                mod += 1

        return mod


class GaussCairns2(GaussCairns):
    col = "Humidity3pm"


class DateSwap(PolluteCellWithProb):
    error_type: ErrorTypes = ErrorTypes.SYNTAX_VIOLATION
    col: str = "Date"
    probability = 0.5

    @classmethod
    def cell_reformat_callback(cls, x):
        date = x.split("-")
        return f"{date[0]}-{date[2]}-{date[1]}"


class WindOutlier(PolluteCellWithProb):
    """Global Outliar"""

    error_type: ErrorTypes = ErrorTypes.OUTLIER
    col: str = "WindSpeed9am"
    probability = 0.01

    @classmethod
    def cell_reformat_callback(cls, x):
        return x * 100


class CityChange(Pollute):
    """Adds a City nearby Albany Australia instead"""

    error_type: ErrorTypes = ErrorTypes.SYNTAX_VIOLATION
    col: str = "Location"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        n = 100
        if len(input.index) < n:
            start = 0
        else:
            start = np.random.randint(0, len(input.index) - 49)
        idx = input.index[start : start + n]
        input.loc[idx, cls.col] = "Yakamia"
        return n


class BrokenWindDir(Pollute):
    error_type: ErrorTypes = ErrorTypes.SYNTAX_VIOLATION
    col: str = "WindDir3pm"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        n = int(len(input.index) * 0.20)
        idx = np.random.choice(input.index, n, replace=False)
        mask = input.loc[idx, cls.col].astype(str).str.len() > 1
        input.loc[idx[mask], cls.col] = input.loc[idx[mask], cls.col].apply(
            lambda x: f"{x[-1]}{x[:-1]}"
        )
        return n


class MaybeRain(Pollute):
    """Maybe it will rain ;)"""

    error_type: ErrorTypes = ErrorTypes.SYNTAX_VIOLATION
    col: str = "RainTomorrow"
    probability = 0.10

    @classmethod
    def cell_reformat_callback(cls, x):
        return "Maybe"


class Outlier(Pollute):
    error_type: ErrorTypes = ErrorTypes.OUTLIER
    col: str = "MaxTemp"

    @classmethod
    def find_percent_range_sequences(cls, arr, tolerance=0.5, min_length=1):
        sequences = []
        n = len(arr)
        start = 0

        while start < n:
            min_val = max_val = arr[start]
            end = start

            for i in range(start + 1, n):
                min_val = min(min_val, arr[i])
                max_val = max(max_val, arr[i])
                if max_val > min_val * (1 + tolerance):
                    break
                end = i

            if end - start + 1 >= min_length:
                sequences.append((start, end, arr[start : end + 1]))

            start = end + 1  # next sequence

        return sequences

    @classmethod
    def find_biggest_n(
        cls, sequences: list[tuple[int, int, np.ndarray]], n: int
    ) -> list[tuple[int, int, np.ndarray]]:
        sequences_sorted = sorted(
            sequences, key=lambda x: x[1] - x[0] + 1, reverse=True
        )
        return sequences_sorted[:n]


class ContextualOutlier(Outlier):
    error_type: ErrorTypes = ErrorTypes.OUTLIER
    col: str = "MaxTemp"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        sorted_df = input.sort_values(["Location", "Date"])
        locations = input["Location"].unique().tolist()
        num_outlier = 0

        for location in locations:
            sorted_location = sorted_df[sorted_df["Location"] == location]

            sequences = cls.find_biggest_n(
                cls.find_percent_range_sequences(sorted_location[cls.col].to_numpy()),
                10,
            )

            for i_start, i_end, _ in sequences:
                idx_pos = random.randint(i_start, i_end)
                idx_label = sorted_location.index[idx_pos]
                sorted_location.at[idx_label, cls.col] = round(
                    sorted_location.at[idx_label, cls.col] * 0.4, 1
                )
                num_outlier += 1
        return num_outlier


class CollectiveOutlier(Outlier):
    error_type: ErrorTypes = ErrorTypes.OUTLIER
    col: str = "Pressure9am"

    @classmethod
    def pollute(cls, input: pd.DataFrame, mask: pd.DataFrame | None = None) -> int:
        sorted_df = input.sort_values(["Location", "Date"])
        locations = input["Location"].unique().tolist()
        num_outlier = 0

        for location in locations:
            sorted_location = sorted_df[sorted_df["Location"] == location]

            sequences = cls.find_percent_range_sequences(
                sorted_location[cls.col].to_numpy(), tolerance=0.02
            )

            for i_start, i_end, _ in random.sample(
                sequences, int(len(sequences) * 0.3)
            ):
                for i in range(i_start, i_end):
                    idx_label = sorted_location.index[i]
                    sorted_location.at[idx_label, cls.col] = round(
                        sorted_location.at[idx_label, cls.col]
                        * random.uniform(0.3, 0.7),
                        1,
                    )
                    num_outlier += 1
        return num_outlier


def main():
    df = pd.read_csv(Path("datasets/weather_subset4_group4.csv"))

    pollution_functions: list[Pollute] = [
        CToF,
        DirToDegree,
        GaussWindSpeed,
        WindOutlier,
        CityChange,
        BrokenWindDir,
        ContextualOutlier,
        CollectiveOutlier,
        GaussCairns,
        GaussCairns2,
        DateSwap,  # swop after the date is needed
    ]
    total_cells = df.shape[0] * df.shape[1]
    mask = pd.DataFrame(0, index=df.index, columns=df.columns)
    polluted = 0
    for pollution_cls in pollution_functions:
        before = deepcopy(df)
        # print(df[pollution_cls.col])
        polluted += pollution_cls.pollute(df)
        # print(df[pollution_cls.col])
        create_pollution_mask(mask=mask, before=before, after=df, cls=pollution_cls)
        # print(mask[pollution_cls.col])
        print(f"Polluted {pollution_cls.col} {round(polluted / total_cells * 100, 0)}%")
        df.to_csv(Path("datasets/weather_subset4_group4_w_errors.csv"), index=False)
        mask.to_csv(
            Path("datasets/weather_subset4_group4_error_mappings.csv"), index=False
        )


if __name__ == "__main__":
    main()
