# Job Scout Memory Rules

Workday jobs with `postingAvailable:false` are expired. Do not append expired
jobs to the workbook, even if the URL shape is structurally valid.

The canonical job workflow requires reading the current source file or live
posting state before taking action.
