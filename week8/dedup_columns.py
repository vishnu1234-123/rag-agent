"""
FilingsIQ - Column deduplication for Docling table extraction (Week 8, Step 3)

Problem: On ~6 of 8 filings tested (Apple, JPMorgan, ExxonMobil - but NOT
Microsoft, and inconsistently even within the same filer across form
types), Docling splits merged/spanned HTML table cells into multiple
IDENTICAL adjacent DataFrame columns instead of one logical column.
The underlying data is correct; only the column structure is wrong.

This module collapses contiguous runs of identical adjacent columns
into a single column, and leaves already-clean tables untouched.

USAGE:
    import pandas as pd
    from dedup_columns import dedup_triplicated_columns

    df_clean = dedup_triplicated_columns(df)
"""

import pandas as pd

def dedup_triplicated_columns(df:pd.DataFrame)->pd.DataFrame:
    """
    Collapse contiguous runs of identical adjacent columns into one column.

    Only ADJACENT columns are checked (never "any two columns anywhere in
    the table"), because the triplication artifact we observed always
    affects immediately neighboring columns - a real, coincidental value
    match between two distant columns (e.g. two different years happening
    to report the same number) must never be collapsed.

    Example: columns [A, A, A, B, C, C] -> [A, B, C]
    Example (Microsoft, already clean): [A, B, C, D] -> [A, B, C, D] (unchanged)

    Args:
        df: DataFrame as returned by table.export_to_dataframe()

    Returns:
        A new DataFrame with duplicate adjacent columns collapsed.
        Column names are reset to 0..N-1 (positional), since Docling's
        raw tables don't carry meaningful column headers at this stage.
    """

    if df.shape[1]<=1:
        return df.copy()

    keep_indices=[0]
    for i in range(1,df.shape[1]):
        prev_kept=keep_indices[-1]
        if df.iloc[:,i].equals(df.iloc[:,prev_kept]):
            continue
        keep_indices.append(i)

    deduped=df.iloc[:,keep_indices].copy()
    deduped.columns=range(deduped.shape[1])
    return deduped 

def summarize_dedup(df_before:pd.DataFrame,df_after:pd.DataFrame)->str:
    if df_before.shape[1]==df_after.shape[1]:
        return f"No Change: {df_before.shape} (already clean)"
    return f"Collapsed {df_before.shape[1]} cols -> {df_after.shape[1]} cols (shape {df_before.shape}->{df_after.shape})"

if __name__ == "__main__":
    # Quick self-test using patterns we actually observed in the data,
    # not synthetic edge cases invented from scratch.

    # Pattern from Apple Table 24 (balance sheet): 3x triplication throughout
    triplicated = pd.DataFrame({
        0: ["Cash and cash equivalents", "Marketable securities"],
        1: ["Cash and cash equivalents", "Marketable securities"],
        2: ["Cash and cash equivalents", "Marketable securities"],
        3: ["$", "18,763"],
        4: ["35,934", "18,763"],
    })
    result = dedup_triplicated_columns(triplicated)
    print("Test 1 (triplicated, like Apple):")
    print(summarize_dedup(triplicated, result))
    assert result.shape[1] == 3, f"Expected 3 columns after dedup, got {result.shape[1]}"
    print("PASSED\n")

    # Pattern from Microsoft Table 25 (balance sheet): already clean, no dupes
    clean = pd.DataFrame({
        0: ["Cash and cash equivalents", "Short-term investments"],
        1: ["$", ""],
        2: ["30,242", "64,323"],
        3: ["$", ""],
        4: ["18,315", "57,228"],
    })
    result2 = dedup_triplicated_columns(clean)
    print("Test 2 (clean, like Microsoft):")
    print(summarize_dedup(clean, result2))
    assert result2.shape[1] == clean.shape[1], "Clean table should be unchanged"
    print("PASSED\n")

    # Pattern from JPM: partial duplication (only some columns triplicated)
    partial = pd.DataFrame({
        0: ["Total net revenue", "Total noninterest expense"],
        1: ["Total net revenue", "Total noninterest expense"],
        2: ["$", "95,640"],
        3: ["182,447", "95,640"],
        4: ["Change", "Change"],
    })
    result3 = dedup_triplicated_columns(partial)
    print("Test 3 (partial duplication, like JPM):")
    print(summarize_dedup(partial, result3))
    assert result3.shape[1] == 4, f"Expected 4 columns after dedup, got {result3.shape[1]}"
    print("PASSED\n")

    print("All self-tests passed.")