# Output Format

Use this fixed structure for the final repository brief.

## Delivery Mode

- Default: inline response
- Save a markdown file only when the user explicitly asks for a document, file, report, or written artifact in a repository path
- Do not silently create files just because the analysis is large

## Required Brief Template

```markdown
## Repository Summary
- What the repository appears to be
- The research goal you optimized for

## Apparent Repository Type
- Short inferred label or primary analysis lens
- Use `mixed` or multiple values when needed

## Relevant Areas
- Which parts of the repository matter most for the user's goal

## Key Files and Directories
- Specific paths to inspect first
- Why each path matters

## Notable Patterns and Design Choices
- Important observed patterns
- Cite concrete local paths for each substantive point

## Observed Facts
- Facts directly grounded in the cloned repository

## Inferences and Confidence
- Interpretations derived from the facts
- Confidence level and remaining uncertainty

## Maintenance and Maturity Signals
- Releases, CI, tests, contributor workflow, maintenance clues

## Caveats and Non-Transferable Parts
- Repo-specific assumptions
- Parts that may not generalize well as references

## Unresolved Questions
- What the repository did not answer clearly

## Evidence
- Local file or directory paths
- Repository URLs for issues, PRs, releases, or docs used as secondary evidence
```

## Evidence Rules

Every substantive claim should cite either:
- a local file or directory path from the cloned repository
- a repository URL for issues, PRs, releases, or docs used as secondary evidence

Do not present polished summaries with no path-level grounding.

## Example Delivery Behavior

- "Research these repository URLs and explain which ones are most relevant to our use case." -> inline response
- "Research this repository and write a 500+ line markdown report in an appropriate location." -> saved markdown document
