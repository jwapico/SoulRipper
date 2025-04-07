# Installation
You need to create a WSL instance with ubuntu

```bash
TODO: instructions
```

Open the WSL instance and paste this in `/etc/wsl.conf`:

```
[boot]
systemd=true

[automount]
enabled=true
mountFsTab=false
```

Then paste this in `~/.bashrc`:

```
sudo mount -t drvfs D: /mnt/d
```

# Configuration

You need to configure cookies for yt-dlp to work. Download the cookies.txt extension, download your cookies for youtube, and put the file in app_data