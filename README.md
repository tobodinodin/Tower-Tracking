# Tower-Tracking
Tower Tracking, is a open-source badge tracking system for Roblox.

# Installation
You have to "pip install" everything thats listed in requirements.txt for it to run locally on your computer.

# History
Tower Tracking was originally developed for the Roblox obbying game "The Soul Crushing Realm". Before going open-source for any fangame owner to set up their own bot.

# Usage
To run the bot, you fist need to go to https://api.towerstats.com/docs and get your API key. Next, go to the Discord Developer Platform, and put them in the config.
In main.py, you will find "MAINTENANCE_MODE = False". This allows you to make no one be able to use the commands untill true, with that theres also the /maintenance true/false command
that you can only use if you replace my ID with your ID.

# How does this work?
Firstly, it gets the ID of the Roblox user, and sends it to the TowerStats API. If the TowerStats API returns empty, then all badges of the player are checked for completions. If the players inventory is privated, then you will get an error message.

# DISCLAIMER
This is currently ONLY for soul crushing difficulties (8-14)
