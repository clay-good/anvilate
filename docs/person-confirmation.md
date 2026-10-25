# Person confirmation

**Some decisions are the engineer's, and the agent cannot make them for you.** Anvilate
asks you for them through your agent's client, records how your answer arrived, and says
so in every result that rests on it.

## The four decisions

| Decision | When it comes up |
| --- | --- |
| Confirm a value your agent read off a picture, a scan or a PDF | The spec cites the file in `sources` with origin `agent_read`. Until you confirm it, the part is drawn and screened as a first look and exports only as unvalidated. |
| Write a file past a failing check | You want the STEP, 3MF, DXF or QIF file anyway. It is written marked unvalidated in the file. |
| Record a review, or accept a failing check as an exception | No MCP tool records one. |
| Agree to download a dataset | Only `anvilate fetch NAME --consent` does it. |

No MCP tool takes any of these as an argument. A test over the tool catalog holds that,
at every depth of every tool's input. If your agent writes `confirmed_by` into a spec it
sends, the call is refused by field name, unless one of your own confirmations below
already backs that exact value under that exact name.

## How you are asked

**If your client can show forms, it shows you one.** MCP calls this elicitation. The form
names the value, the file and where in it the agent read it, and asks you to tick that you
checked it and give your name. For a file past a failing check, it names the file and the
check that failed. Accept with the box ticked and a name, and it is recorded. Anything else
(decline, close the form, leave the box unticked) is recorded as a decline, and you are not
asked about that value again.

Clients on the current protocol revision receive the question as an input-required result
and send the call again with your answer. Older clients declared the capability when they
connected, and Anvilate sends them the form as a request of its own. Either way, the agent
sees the call finish once, with your answer applied.

**If your client cannot show forms**, nothing is asked. The values stay drafts, the card
says how to confirm them, and a file past a failing check is refused with the two things
you can do yourself:

- Run `anvilate confirm` with the subject handle the agent's result returned. It shows each
  value the agent read, asks your name, and records each value you type yes to. It runs
  only at an interactive terminal and refuses anything else.
- Write a confirmation file in the output folder's `confirmations` directory. The refusal
  prints the file's exact contents, with the subject digest it confirms. For a failing
  check, `anvilate build --unvalidated` at the shell also still works.

```bash
anvilate confirm sha256:3f1c0e9a2b7d4c6e8f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6
```

## What each channel proves

Each confirmation carries its channel in the spec (`confirmed_via`), on the card line, and
in the evidence bundle, which lists every confirmation the spec rests on and says whether
any of them is attested to a person.

| Channel | Reads as | What it proves |
| --- | --- | --- |
| Interactive terminal | confirmed by *name* at an interactive terminal | Somebody was at a terminal and typed the name. This is the only channel recorded as attesting a person. |
| Elicitation | answered through *client and version*, naming *name* | The client relayed that answer. It does not show who gave it, so it never reads "confirmed by". |
| Confirmation file | confirmed by *name* in a confirmation file | A file with that content is in the output folder. Anvilate cannot see who wrote it. |
| Written into the document | confirmed by *name* | Your own spec at the shell. Over MCP it is refused unless a record above backs it. |

A confirmation confirms one exact thing: one value read from one file, or one file of one
spec. Change the value, the cited file or the spec, and it confirms nothing.

Anvilate verifies no identity. A local agent with a shell could run commands or write files
it should not, and nothing on your machine can prevent that. What this design does is stop
an agent from doing it by filling in a field. A confirmation is never something it can
write in passing, and every channel is reported as what it is.

## Where records live

Confirmations made through a form or at a terminal are kept beside the subject store, under
the dataset cache (`$ANVILATE_DATA_HOME`), keyed by what they confirm. Every server instance
reads them, and no server needs to remember a call. Declines live there too. Delete a
decline's file to be asked again.
