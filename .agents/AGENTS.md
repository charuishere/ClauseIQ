<RULE[administrative_files_override]>
**Administrative Files Auto-Update Override:**
Despite the global rule against automatic file modifications, you have EXPLICIT PERMISSION to automatically edit, update, and manage administrative files without asking for user confirmation. 
Administrative files strictly include:
- `LEARNINGS.md`
- `logs.txt`
- `DAY_<N>_CHECKLIST.md`

**Formatting Constraints for logs.txt:**
When updating `logs.txt`, you must ensure it remains exceptionally clear, readable, and understandable. 
- Use simple, human-readable bullet points.
- Avoid dumping raw terminal output or overly dense technical jargon.
- Group entries logically by task or day.

Always use your automatic tools to keep these files up to date immediately after a step completes, without prompting the user to do it manually.
</RULE[administrative_files_override]>

<RULE[minor_bugfix_override]>
**Minor Bug Fix Auto-Execution Override:**
Despite the global rule against automatic file modifications and git commands, you have EXPLICIT PERMISSION to automatically edit files, commit the change, and push to GitHub for **minor, 1-line bug fixes** (e.g. fixing typos, fixing import paths, correcting dictionary syntax).

**Constraint:** Whenever you perform an automatic bug fix, you MUST clearly and explicitly communicate the exact change to the user in your response. You must state:
- The file name
- What the code used to be (From what)
- What the code was changed to (To what)
- Why the change was made
</RULE[minor_bugfix_override]>

<RULE[ci_cd_deployment]>
**CI/CD Deployment Enforcement:**
Never manually build or deploy the backend infrastructure or code locally (e.g., using `sam build`, `sam deploy`, or similar deployment tools). 

All backend compilation and deployment are automatically handled by the GitHub Actions CI/CD pipeline upon pushing to the repository. Whenever backend changes are made, rely exclusively on `git push` to deploy them.
</RULE[ci_cd_deployment]>
