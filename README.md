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
options = "metadata,umask=22,fmask=11"
mountFsTab=false
```

If you want to download to an external drive, paste this in `~/.bashrc` (change drive name if needed):

```
sudo mount -t drvfs D: /mnt/d
```

You also need to edit this line of `docker-compose.yml`:

```
     - /mnt/d/DJ/Music/souls/:/mnt/d/DJ/Music/souls
```

# Configuration

You need to configure cookies for yt-dlp to work. Download the cookies.txt extension, download your cookies for youtube, and put the file in app_data