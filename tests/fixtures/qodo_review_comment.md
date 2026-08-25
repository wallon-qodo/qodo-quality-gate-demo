<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (2)</code>  <code>📘 Rule violations (1)</code>  <code>🧑 Team insights (0)</code>  <code>📜 Skill insights (1)</code>  <code>🛡 Security issues (0)</code>

<br/>

<img src="https://img.shields.io/badge/Critical-634FD1?style=flat-square" height="20px" alt="Action required">

<details>
<summary>  1.  Reapply failure ignored <code>🐞 Bug</code> <code>☼ Reliability</code> <code>⭐ New</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>When the findings comment is overwritten during the watch phase, the script calls
><b><i>apply_to_review(...)</i></b> but ignores its return value, so repeated PATCH failures can silently
>leave the advisory missing for the remainder of the run.
></pre>
></details>

> <details open>
><summary>Code</summary>
><br/>
>
><code>[.qodo/ci/churn_comment.py[R169-171]](https://example.invalid/pull/1/files#R169-R171)</code>
>
>```diff
>+        apply_to_review(a.repo, a.pr, section, a.tmp)
>```
></details>

</details>


<details>
<summary>  2.  <s>Missing issues write permission</s> <code>✓ Resolved</code> <code>📘 Rule violation</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The workflow declares <b><i>pull-requests: write</i></b> but edits an issue comment, which needs
><b><i>issues: write</i></b> on this API surface, so the PATCH fails with 403 on a fresh checkout.
></pre>
></details>

</details>


<br/>

<details><summary><ins><strong>View warning (1)</strong></ins></summary><br/>
<img src="https://img.shields.io/badge/Warning-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

<details>
<summary>  3.  <b><i>gh_json()</i></b> silently drops errors <code>📜 Skill insight</code> <code>☼ Reliability</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>gh_json()</i></b> returns <b><i>None</i></b> when <b><i>gh api</i></b> fails or when JSON decoding fails, without
>logging any context, so real API errors become indistinguishable from “no comments found”.
></pre>
></details>

</details>

</details>
