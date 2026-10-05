/* Which edges of a scroll region have more content beyond them. A dialog body
 * draws its top/bottom shade only for these, so a short body is flat. A
 * one-pixel tolerance absorbs fractional scroll positions on zoomed screens. */
export function scrollEdges(scrollTop: number, clientHeight: number, scrollHeight: number, tolerance = 1) {
  return {
    above: scrollTop > tolerance,
    below: scrollHeight - clientHeight - scrollTop > tolerance,
  };
}
