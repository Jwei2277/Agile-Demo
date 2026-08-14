name: "User Story"
description: Template for a student-friendly user story with acceptance criteria
labels: ["story"]
body:
  - type: textarea
    id: story
    attributes:
      label: As a … I want … so that …
      description: Write the user story in one sentence.
      placeholder: As a student, I want to add a todo so that I remember my tasks.
  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance Criteria (Gherkin)
      description: List Given/When/Then scenarios.
      value: |
        **Scenario:** Add a todo
        Given I have the API running
        When I POST /items with a new item
        Then I receive 201 and the item is persisted
  - type: checkboxes
    id: definition-of-done
    attributes:
      label: Definition of Done checklist
      options:
        - label: Tests added and passing (CI green)
        - label: Linting passes
        - label: Documentation/README updated if needed
        - label: Stakeholder reviewed (PR approved)
