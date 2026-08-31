# Small Workflow Automation Demo

Owned demonstration — not client work.

This file-based sample takes made-up form entries, checks that the needed
information is present, avoids duplicate work, and adds ready items to an owner
review queue. Missing or repeated entries are listed for review. It makes no
external calls and sends no customer messages.

The sample is intentionally small. It proves a pattern that can be adapted to
one agreed file-based business process or one buyer-owned tool in a safe test
setup. A connection between two online tools needs a separate connector check
before it can be quoted. The exact tools and access method must be confirmed
before an order starts.

## What the sample shows

- Two complete example entries become two items for an owner to review.
- A repeated entry does not create a second task.
- An entry missing required information is listed for review instead.
- Extra input fields are not copied into the output.
- Repeated runs produce the same files.
- The run receipt confirms that the demonstration made no outside calls and
  sent no messages.

## Run the demonstration

From this directory:

```bash
python3 run_workflow.py \
  --input fixtures/made_up_inquiries.csv \
  --rules workflow_rules.json \
  --output-dir sample-output
```

The result contains:

- `team_work_queue.csv`: two ready items for the made-up owner.
- `exceptions.csv`: one repeated entry and one entry missing information.
- `run_receipt.json`: file fingerprints and proof that no external calls or
  messages occurred.

Run the test suite with:

```bash
python3 -m unittest discover -s tests -v
```

## Limits

- Made-up information only; no real person or customer records.
- No website, hosted app, database, vendor account, key, or password.
- No email, text, phone call, webhook, form submission, or live-system update.
- No claim of client results, time savings, leads, revenue, or production
  reliability.
- Your team reviews the test and decides whether to turn a future workflow on.

## Ask about a small workflow

Allure Labs offers three starting points:

- **$125 Workflow Plan:** map one repetitive process and provide a practical
  build and test plan.
- **$500 Small Automation Build:** build and test one small file-based workflow
  or one workflow inside a buyer-owned tool.
- **$1,250 Automation Repair:** diagnose and repair one existing workflow after
  confirming that the exact tools can be tested safely.

[See the full package limits and start by email without a GitHub account](https://offers.allurelabs.ai/workflow-automation/).

[Open a public, structured implementation request](https://github.com/Allura-Gensin/small-workflow-automation-demo/issues/new?template=implementation-request.yml&title=%5Bpublic-workflow-demo%5D%20Implementation%20request).
Do not include passwords, access keys, customer records, personal information,
or private business details. A request starts a scope conversation; it is not
an order, contract, reservation, payment, or authorization to access a system.
