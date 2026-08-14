name: "Bug Report"
description: Report a bug with steps and expected/actual behavior
labels: ["bug"]
body:
  - type: textarea
    id: summary
    attributes:
      label: Summary
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      value: |
        1.
        2.
        3.
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior & Logs
  - type: input
    id: version
    attributes:
      label: App version/commit
