# Automatically download new audiobooks on schedule
This documentation shows how to schedule automatic downloading of audiobooks 
added to the connected audible library. AudiblePodcastFeed has no scheduling 
built-in so an external tool must be used if automatic downloading is desired.

This document assumes you are using the `docker-compose.yml` provided by the 
project. Specifically that the service executing `library_downloader.py` is 
named `audible-podcasts-downloader`.

## General
Start the `audible-podcasts-downloader` service in the desired interval. This 
can be done by running `docker compose up audible-podcasts-downloader` in the
directory where the `docker-compose.yml` is located.

## Example with systemd timers
To use systemd to automate this, place the following [unit files](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html)
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
<summary>Explanation of [the service unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)</summary>
The service unit tells systemd to run the command `docker compose up audible-podcasts-downloader` 
in the the working directory `{{ absolute path to docker-compose.yml directory }}`.
By default all systemd units execute the commands with root permissions.
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
<summary>Explanation of [the timer unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)</summary>
The timer unit tells systemd that to run when the wall clock time has 00 or 30 
in the minutes. A random delay of up to 600 seconds is added each time. Combined
the wall clock sheduling with the random delay mean, that the service is 
executed twice an hour:
* 0-10 minutes after the full hour
* 30-40 minutes after the full hour

The service is only executed when the `docker.service` exists and is running. 
To allow enabeling the timer unit on system boot it is marked as wanted by 
`timers.target`.
</details>

Make sure that the `.service` and `.timer` unit have the exact same name before 
the file extension. [This name is what systemd uses to select what service to 
activate for the timer.](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html#Description)

After creating the files reload the systemd daemon, enable and activate the 
timer unit:
```bash
systemctl daemon-reload
systemctl enable --now audible-download-books.timer`
```
To check the status of the timer and service units the `systemctl status` 
command can be used:
```bash
systemctl status audible-download-books.timer
systemctl status audible-download-books.service
```