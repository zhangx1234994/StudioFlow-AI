# UI Interaction Contract (v1)

## Purpose
Define a single interaction model for all tool workspaces so users always know current step, system status, and next action.

## Unified State Machine
- `idle`: No active operation; current step is actionable.
- `submitting`: User just clicked a primary action; request in-flight; primary actions locked.
- `running`: Background generation in progress; progress/logs update continuously.
- `review`: Outputs available and awaiting manual review.
- `done`: Required outputs reviewed or accepted.
- `failed`: Operation failed with actionable reason and retry path.
- `blocked`: User attempted to jump to a step with unmet prerequisites.

## Core Interaction Rules
1. Each step has exactly one primary CTA.
2. Primary CTA must show feedback in <=200ms (`已提交...`).
3. While `submitting` or `running`, all conflicting actions are disabled.
4. Step navigation enforces prerequisites; blocked navigation redirects to prerequisite step with reason.
5. Progress feedback is persistent and cannot regress to `等待执行` until state exits `running`.
6. Every failure state includes: reason, retry action, and suggested next step.

## Step Gating Rules
- `overview`: Always accessible.
- `plan`: Always accessible.
- `generate`: Requires `plan_ready && prompts_ready`.
- `review`: Requires at least one generated asset.
- Intro video extras:
  - Render requires selected script.
  - If storyboard exists and not confirmed, user is guided to approve/confirm storyboard first.

## Required UI Feedback Blocks
- Global status bar: project-level stage + task status + next action.
- Flow guide bar: "where you are / what is happening / where to click next".
- Step status bar: step-local execution status.
- Timeline logs: latest events for trust and recovery.

## Edge Cases to Handle
- Repeated clicks on primary CTA.
- Refresh during long-running tasks.
- Partial completion (some assets succeed, some fail).
- Task timeout or provider error.
- User edits prompts after plan generated (must mark downstream stale if needed).

## Acceptance Criteria
- No primary action has silent click behavior.
- No blocked step is entered without explanation.
- Running operations preserve visible progress language.
- Refresh restores correct step and actionable state.
