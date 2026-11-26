import * as React from "react";

/* Maps the Radix-style `asChild` convention onto a ui-sdk part's `render`
 * prop: the single child element becomes the rendered element, its own
 * children become the part's content, and props and refs merge. */
export function asChildRender(asChild: boolean | undefined, children: React.ReactNode) {
  if (!asChild || !React.isValidElement<{ children?: React.ReactNode }>(children)) {
    return { children };
  }
  return { render: children, children: children.props.children };
}
