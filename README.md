# LocalPilot

I wanted to build a developer tool using the computer-use capabilities of frontier AI models. I was inspired by ChatGPT's computer-use skill and wanted to try building my own version.

For LocalPilot, I decided to run the model locally on my Windows laptop instead of calling a cloud AI service. I gave it an Ubuntu virtual machine where it could use a terminal, open applications, browse websites, and work with files. I also wanted to access that computer from my iPhone, so I could give it a task and watch what it was doing without sitting at my laptop.

The idea was to give the model a personal computer it could actually use to get things done.

## What it does

LocalPilot has a web app with two views: **Agent** and **Desktop**. In Agent, I can describe a task and see its progress and results. In Desktop, I can watch the Ubuntu screen and take control myself.

The model can create and edit files, run approved commands, open Firefox, interact with the desktop, and install a small set of supported tools. I can approve or reject actions, cancel a task, or pause the AI while I use the computer. There's also an optional setting to automatically approve a limited set of routine commands.

The current version uses a local 27B model through Ollama. Windows runs the model on the laptop GPU, while Ubuntu provides the computer it works in. Tailscale lets me reach it privately from my iPhone. The web app can be added to the iPhone Home Screen.

## What I tested myself

I used my iPhone 15 Pro Max over mobile data to connect to the Linux desktop and control it. From the phone, I also tried:

- Asking the agent to create and run a Python script that printed a greeting.
- Creating a folder and opening it in the file manager.
- Taking manual control of the desktop while the AI was paused.
- Reviewing and approving a software installation.
- Opening websites in Firefox, including the PlayStation website.
- Installing the web app on my Home Screen and checking the dark interface.

I also restarted my laptop to check whether the setup came back. The first restart exposed a connection problem that caused a 502 error. That was fixed, and the app and desktop worked again after the later restart checks.

There are automated tests too, covering permissions, approvals, cancellation, connection handling, backups, and other parts of the system. A separate task evaluation checked things like fixing a small Python program, summarizing a CSV, and handling a missing file. The methods and results are in [docs/](docs/).

## Where it stands

This is a working personal prototype. It handles the tasks I've tested, but I wouldn't assume it can reliably complete any long or unfamiliar task without supervision. It still asks before running scripts, installing software, or controlling the desktop. Routine auto-approval only covers a fixed list of simple commands.

The laptop needs to be awake, signed in, and online while I use it from my phone. Running the model locally doesn't make the whole setup work offline. The current focus is iPhone access and one local model.

## Documentation

The technical details live in [docs/](docs/):

- [Setup, daily use, and troubleshooting](docs/setup-and-operation.md)
- [Architecture and permissions](docs/architecture.md)
- [Task evaluation](docs/task-evaluation.md)
- [Routine auto-approval](docs/auto-approval.md)
- [Backup and restore](docs/backup-and-restore.md)
- [Changelog](docs/CHANGELOG.md)

If you're looking through the code, start with the [contribution guide](CONTRIBUTING.md) and [security notes](SECURITY.md). Private configuration, credentials, VM files, and task history belong in the ignored `.local/` directory and should never be uploaded.
