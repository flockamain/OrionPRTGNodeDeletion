pip install -r requirements.txt while in the folder

input credentials into config.py -- prtg server requires the "https://" before it, orion server does not - it is auto added

run ->

attempts login

if credentials are bad, it will either tell you it is missing or that it cannot login using those credentials

Once logged in, verifies we can get data from the servers

Asks for search term
It will search both servers for nodes matching what was put in
If search is too short, it will let you know and ask if you want to stop

If good, looks in both servers for the device
If there is a single node in each, it will ask if you'd like to delete from both
If single node in one or the other, asks if you'd like to delete from the one.

Passive confirmation - if there is only a single node, proceed
Active confirmation - if you type in a sentence, you can actually delete the single node. If not exact or nothing typed in - do not delete

Logic allows us to continue if we want and search for more.
