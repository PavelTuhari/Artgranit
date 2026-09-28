# DFM -> Xcode Visual Forms Mapping

This folder contains visual-source analogs of Delphi `*.dfm` forms for the Xcode project.

## Mapping

- `uAccountingChild.dfm` -> `AccountingForm.xib`
- `uCashierChild.dfm` -> `CashierForm.xib`
- `uAdminChild.dfm` -> `AdminForm.xib`

## Notes

- Runtime UI is still implemented in SwiftUI (`ContentView.swift`) for current build.
- These XIBs are editable visual form sources (Interface Builder), similar in purpose to DFM files.
- If you want, next step is full runtime migration from SwiftUI to AppKit controllers that load these XIB files directly.
