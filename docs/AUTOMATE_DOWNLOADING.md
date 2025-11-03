# Automatically download new audiobooks on a schedule
This document shows how to schedule automatic downloading of audiobooks added to
the connected audible library. AudiblePodcastFeed has no scheduling built-in so 
an external tool must be used if automatic downloading is desired.

This document assumes you are using the `docker-compose.yml` provided by the 
project. Specifically that the service executing `library_downloader.py` is 
named `audible-podcasts-downloader`.

## General
Start the `audible-podcasts-downloader` service in the desired interval. This 
can be done by running `docker compose up audible-podcasts-downloader` in the
directory where the `docker-compose.yml` is located.

## Example with systemd timers
To use systemd to automate this, place the following [**unit files**](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html)
in `/etc/systemd/system/`:

`audible-download.books.service`:
```
[Unit]
Description=Audible books downloader

[Service]
WorkingDirectory={{ absolute path to docker-compose.yml directory }}
ExecStart=docker compose up audible-podcasts-downloader
```
<details>
<summary>Explanation of <a href="https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html">the service unit</a></summary>
The <i>service unit</i> tells systemd to run the command 
<code>docker compose up audible-podcasts-downloader</code> in the the 
working directory <code>{{ absolute path to docker-compose.yml directory }}</code>.
By default all systemd units execute commands with root permissions.
</details>

`audible-download-books.timer`:
```
[Unit]
Description=Run audible book downloader every half hour
Requires=docker.service
After=docker.service

[Timer]
RandomizedDelaySec=600
OnCalendar=*-*-* *:00,30:00

[Install]
WantedBy=timers.target
```
<details>
<summary>Explanation of <a href="https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html"> the timer unit</a></summary>
The timer unit tells systemd to run the <i>systemd service</i>, when the 
wall clock time has 00 or 30 in the minutes. A random delay of up to 600 seconds 
is added each time. Combined the wall clock sheduling with the random delay mean, 
that the <i>systemd service</i> is executed twice an hour:
<ul>
<li>0-10 minutes after the full hour</li>
<li>30-40 minutes after the full hour</li>
</ul>

The <code>audible-download-books</code> *systemd service* is only executed when 
the <code>docker</code> *systemd service* exists and is running. To allow 
enabeling the timer unit on system boot, it is marked as wanted by 
<code>timers.target</code>.
</details>

Make sure that the `.service` and `.timer` unit files have the exact same name 
before the file extension. [This name is what systemd uses to select what 
*systemd service* to activate for a timer.](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html#Description)

After creating the *unit files* reload the systemd daemon, enable and activate 
the timer unit:
```bash
systemctl daemon-reload
systemctl enable --now audible-download-books.timer
```
To check the status of the *timer and service units* the `systemctl status` 
command can be used:
```bash
systemctl status audible-download-books.timer
systemctl status audible-download-books.service
```
