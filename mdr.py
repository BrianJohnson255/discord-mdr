import asyncio
import discord
import random
import time
import threading
import os

TOKEN = '' # Client token goes here; this has been removed from the repo for security reasons.

client = discord.Client()

roleList = list() # Dead role is at index 0
playerList = list()
isRunning = False
house = None
originalVoice = None

@client.event
async def on_message(message):
	global roleList
	global playerList
	global isRunning
	global house
	global originalVoice

	if message.author == client.user:
		return
		
	elif message.content.startswith(">--begin"):
		numMurderers = 1
		houseType = 1
		
		if len(message.content.split(" ")) > 1:
			numMurderers = int(message.content.split(" ")[1])
			
		if len(message.content.split(" ")) == 3:
			houseType = int(message.content.split(" ")[2])
			
		# Get everyone currently in the voice channel of the person running the command
		voice_state = message.author.voice
		if (voice_state == None):
			await message.channel.send("You are not in a voice channel!")
			return
		
		vc = voice_state.channel
		originalVoice = vc
		vc_members = vc.members
	
		# Creates a channel category
		mc = await message.guild.create_category_channel("Discord Murder")
		
		# Creates the house (essentially a room layout)
		mh = House("Murder House", houseType)
		house = mh
		
		# Keep @everyone from seeing the rooms and per-player text channels
		owEveryone = discord.PermissionOverwrite(create_instant_invite=False, manage_channels=False, manage_webhooks=False, read_messages=False, send_messages=False, send_tts_messages=False, manage_messages=False, embed_links=False, read_message_history=False, mention_everyone=False, external_emojis=False, add_reactions=False, connect=False, mute_members=False, deafen_members=False)
		
		# Initialize the deadRole, set overwrites for regular rooms, and put in the roleList.
		deadRoom = Room("Dead")
		
		deadRole = await message.guild.create_role(name="Dead")
		deadRoom.setRole(deadRole)
		
		owDead = discord.PermissionOverwrite(read_messages=True, send_messages=False, connect=False, speak=False)
		roleList.append(deadRole)
		
		# Create dead VC
		owDeadVC = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
		overwrites = { message.guild.default_role: owEveryone, deadRole: owDeadVC }
		
		deadVC = await mc.create_voice_channel("Dead", overwrites=overwrites)
		deadRoom.setVC(deadVC)
		
		# Creates a role for each room, sets permission overwrites accordingly, and assigns the room VC to the room object.
		for r in mh.rooms:
			role = await message.guild.create_role(name=r.name)
			roleList.append(role)
			
			r.setRole(role)
			owRole = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
			
			overwrites = { role: owRole, message.guild.default_role: owEveryone, deadRole: owDead }
			
			newVC = await mc.create_voice_channel(name=r.name, overwrites=overwrites)
			r.setVC(newVC)
			
		mh.rooms.append(deadRoom)
			
		# Creates the player directory embed, which is given to each player's text channel.
		i = 1
		
		directory = discord.Embed()
		directory.title = "Player List"
		directory.description = "Use this directory to reference players in special commands (`stab 3` would execute the kill command on player number 3, if you are the murderer). This message has been pinned for future reference."
		directory.colour = 0x999999
		
		for m in vc_members:
			# Creates a role for each player, adds it to the roleList, and sets permission overwrites accordingly
			role = await message.guild.create_role(name=m.display_name)
			roleList.append(role)
			
			owRole = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, add_reactions=True)
			
			overwrites = { message.guild.default_role: owEveryone, role: owRole }
			
			# Creates a text channel for each player (that only that player can see)
			tc = await mc.create_text_channel(m.display_name, overwrites=overwrites)
			editedRoles = m.roles
			editedRoles.append(role)
			editedRoles.append(mh.rooms[0].role)
			
			# Assigns the player their respective role and moves them to the main room of the house
			await m.edit(roles=editedRoles, voice_channel=mh.rooms[0].vc)
			#await m.edit(roles=editedRoles)
			
			p = Player(m, i, tc, None, None, mh.rooms[0])
			
			# Adds the player to the player directory
			directory.add_field(name="========================", value=("**" + str(i) + "** : " + p.member.display_name), inline=False) 
			
			i = i + 1
			
			# Adds the player to the playerList and to the room occupant list.
			playerList.append(p)
			mh.rooms[0].players.append(p)
			
		# Decide who the murderer is
		chanceList = playerList.copy()
		murderList = list()
		
		while numMurderers > 0:
			mdrChance = 1 / len(chanceList)
			rolledIndex = int(random.random() / mdrChance)
			
			chanceList[rolledIndex].team = "Murderer"
			chanceList[rolledIndex].job = "Murderer"
			chanceList[rolledIndex].gunEligible = False
			murderList.append(chanceList[rolledIndex])
			
			del chanceList[rolledIndex]
			numMurderers = numMurderers - 1
		
		# Decide who will get the gun
		if len(chanceList) != 0:
			gunChance = 1 / len(chanceList)
			rolledIndex = int(random.random() / gunChance)
			
			chanceList[rolledIndex].team = "Innocent"
			chanceList[rolledIndex].job = "Sheriff"
			
			del chanceList[rolledIndex]
		
		for c in chanceList:
			c.team = "Innocent"
			c.job = "Innocent"
			
		for p in playerList:
			j = await p.tc.send(embed=getJobEmbed(p.job))
			await j.pin()
			
			if p.job == "Murderer" and len(murderList) > 1:
				e = discord.Embed()
				e.title = "A Murderous Alliance..."
				e.description = "Your allies are:"
				e.colour = 0xFF0000
				
				for i in range(0, len(murderList)):
					if murderList[i] != p:
						e.add_field(name="========================", value=murderList[i].member.display_name, inline=False)
						
				a = await p.tc.send(embed=e)
				await a.pin()
			
			dir = await p.tc.send(embed=directory)
			await dir.pin()
		
			msg = await p.tc.send(embed=getNavEmbed(mh.rooms[0]))
			await addNavReactions(msg, mh.rooms[0])
			
		isRunning = True
		
		
	elif message.content.startswith("stab") and isRunning and findPlayer(message.author).job == "Murderer":
		params = message.content.split(" ")
		
		murderer = findPlayer(message.author)
		
		# If no parameter is given
		if len(params) == 1:
			e = discord.Embed()
			e.title = "Command error!"
			e.description = "No player number was given! Try again with a player number (`stab 3`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
		
		if int(params[1]) <= 0 or int(params[1]) >= len(playerList) + 1:
			e = discord.Embed()
			e.title = "Invalid player number!"
			e.description = "Try another number (`stab 3`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
			
		stabee = getPlayerWithNumber(int(params[1]))
		
		if stabee == murderer:
			e = discord.Embed()
			e.title = "You can\'t stab yourself!"
			e.description = "If you are experiencing suicidal thoughts, please call 1-800-273-8255 for help."
			e.colour = 0xFF0000
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		if stabee.job == "Murderer":
			e = discord.Embed()
			e.title = "You can\'t stab a fellow murderer!"
			e.description = "That\'s obviously against the Murderers\' Union Code of Conduct!"
			e.colour = 0xFF0000
			await message.channel.send(embed=e, delete_after=5.0)
			return
		
		if murderer.room.name != stabee.room.name:
			e = discord.Embed()
			e.title = "Target is not in the same room as you!"
			e.description = "You must target someone in the same room as you"
			e.colour = 0xFF0000
			await message.channel.send(embed=e, delete_after=5.0)
			return
		
		if stabee.dead == True:
			e = discord.Embed()
			e.title = "That player has already been stabbed!"
			e.description = "You monster."
			e.colour = 0xC20000
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		stabee.dead = True
		stabee.isMoving = False
		
		# Notify the murderer that they stabbed someone
		mNotify = discord.Embed()
		mNotify.title = "You have stabbed " + stabee.member.display_name + "!"
		mNotify.description = "\"They ran into the knife themselves, I promise!\""
		mNotify.colour = 0xC20000
		await message.channel.send(embed=mNotify, delete_after=10.0)
		await moveToDeadChat(stabee, murderer)
		
		for p in murderer.room.players:
			if p != stabee or p != murderer:
				e = discord.Embed()
				e.title = stabee.member.display_name + " has been murdered!"
				e.description = "That\'s kind of a big uh oh if you ask me."
				e.colour = 0xFF0000
				await p.tc.send(embed=e, delete_after=10.0)
				
		await message.delete()
		
		# Check if all innocents are deadified
		for p in playerList:
			if p.dead == False and p.team == "Innocent":
				return
				
		e = discord.Embed()
		e.title = "GAME OVER! MURDERERS WIN!"
		e.description = "Quite a bloodbath honestly"
		e.colour = 0xAB0000
		
		for p in playerList:
			await p.tc.send(embed=e)
			if p.dead == False:
				await p.member.move_to(house.rooms[len(house.rooms) - 1].vc)
			
		isRunning = False
				
	
	elif message.content.startswith("shoot") and isRunning and findPlayer(message.author).job == "Sheriff":
		params = message.content.split(" ")
		
		shooter = findPlayer(message.author)
		
		# If no parameter is given
		if len(params) == 1:
			e = discord.Embed()
			e.title = "Command error!"
			e.description = "No player number was given! Try again with a player number (`shoot 3`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
			
		if int(params[1]) <= 0 or int(params[1]) > len(playerList):
			e = discord.Embed()
			e.title = "Invalid player number!"
			e.description = "Try another number (`shoot 3`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
		
		shotee = getPlayerWithNumber(int(params[1]))
		
		if shotee.number == shooter.number:
			e = discord.Embed()
			e.title = "You can\'t shoot yourself!"
			e.description = "If you are experiencing suicidal thoughts, please call 1-800-273-8255 for help."
			e.colour = 0x003980
			await message.channel.send(embed=e, delete_after=5.0)
			return
		
		if shooter.room.name != shotee.room.name:
			e = discord.Embed()
			e.title = "Target is not in the same room as you!"
			e.description = "You must target someone in the same room as you"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		if shotee.dead == True:
			e = discord.Embed()
			e.title = "That player has already been shot!"
			e.description = "\"Stop, he's already dead!\""
			e.colour = 0xC20000
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		shotee.dead = True
		shotee.isMoving = False
		
		# Notify the sheriff that they shot someone
		mNotify = discord.Embed()
		mNotify.title = "You have shot " + shotee.member.display_name + "! Their role was: " + shotee.team + "!"
		mNotify.description = "The fastest lead delivery service in town!"
		mNotify.colour = 0x003980
		await message.channel.send(embed=mNotify, delete_after=10.0)
		
		if shotee.team == "Innocent":
			shooter.job = "Innocent"
			shooter.gunEligible = False
			shooter.room.items.append(("Gun", "Gun"))
			
			e = discord.Embed()
			e.title = "You shot an innocent! You have dropped the gun and cannot use it again."
			e.description = "\"It was at this moment, they knew... they f*cked up\""
			await shooter.tc.send(embed=e)
		
		await moveToDeadChat(shotee, shooter)
		
		e = discord.Embed()
		
		for p in playerList:
			if p.room == shooter.room and p != shotee:
				e.title = shooter.member.display_name + " has shot " + shotee.member.display_name + "!"
				e.description = "Looks like they lost American Roulette"
				e.colour = 0x003980
				await p.tc.send(embed=e, delete_after=10.0)
				
			if p.room != shooter.room and p != shotee:
				e.title = "You hear a gunshot through the walls..."
				e.description = "Something\'s going down, but thankfully not here."
				e.colour = 0xF2B91B
				await p.tc.send(embed=e, delete_after=10.0)
				
		await message.delete()
		
		# Check if all murderers are deadified
		for p in playerList:
			if p.dead == False and p.team == "Murderer":
				return
		
		# End the game since this code only runs if no innocents are left alive
		e = discord.Embed()
		e.title = "GAME OVER! INNOCENTS WIN!"
		e.description = "Who says violence doesn\'t solve everything!"
		e.colour = 0xAB0000
		
		for p in playerList:
			await p.tc.send(embed=e)
			if p.dead == False:
				await p.member.move_to(house.rooms[len(house.rooms) - 1].vc)
			
		isRunning = False
		
	elif message.content.startswith("check") and isRunning:
		params = message.content.split(" ")
		
		checker = findPlayer(message.author)
		
		if len(params) == 1:
			e = discord.Embed()
			e.title = "Command error!"
			e.description = "No item number was given! Try again with an item number (`check 1`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
		
		if len(checker.room.items) == 0:
			e = discord.Embed()
			e.title = "Nothing here to check!"
			e.description = "Can\'t check what you can\'t see."
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		if checker.room.items[int(params[1])][0] != "Body":
			e = discord.Embed()
			e.title = "This item is not a body!"
			e.description = "Not sure how you mistook this for a body, but, you know, whatever."
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		e = discord.Embed()
		e.title = checker.room.items[int(params[1])][1].member.display_name + " was " + checker.room.items[int(params[1])][1].job + "!"
		e.description = "Good thing they wrote down what they were in their wallet!"
		e.colour = 0x16BD00
		await message.channel.send(embed=e, delete_after=10.0)
		
		await message.delete()
		
	elif message.content.startswith("get") and isRunning:
		params = message.content.split(" ")
		
		getter = findPlayer(message.author)
		
		if len(params) == 1:
			e = discord.Embed()
			e.title = "Command error!"
			e.description = "No item number was given! Try again with an item number (`get 1`, for example)"
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=10.0)
			return
		
		if len(getter.room.items) == 0:
			e = discord.Embed()
			e.title = "Nothing here to check!"
			e.description = "Can\'t check what you can\'t see."
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		if getter.room.items[int(params[1])][0] != "Gun":
			e = discord.Embed()
			e.title = "This item is not a gun!"
			e.description = "Not sure how you mistook this for a gun, but, you know, whatever."
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		if getter.gunEligible == False:
			e = discord.Embed()
			e.title = "You are not eligible to pick up the gun!"
			e.description = "The gun has deemed you unworthy...probably because you\'ve murdered someone."
			e.colour = 0xEDC31C
			await message.channel.send(embed=e, delete_after=5.0)
			return
			
		getter.job = "Sheriff"
		getter.room.items.remove(("Gun", "Gun"))
			
		e = discord.Embed()
		e.title = "You have picked up the gun!"
		e.description = "You can now shoot the gun with the command `shoot <player number>`! This message has been pinned for future reference."
		e.colour = 0x16BD00
		msg = await message.channel.send(embed=e)
		await msg.pin()
		
		for p in playerList:
			if p.room == getter.room:
				await p.tc.send(embed=getter.room.getRoomStatus())
		
		await message.delete()

	elif message.content.startswith(">--delete"):
		for p in playerList:
			await p.member.move_to(originalVoice)
	
		for c in message.guild.categories:
			if c.name == "Discord Murder":
				for v in c.voice_channels:
					await v.delete()
					
				for t in c.text_channels:
					await t.delete()
					
				await c.delete()
				break
				
		for r in roleList:
			await r.delete()
			
		roleList = list()
		playerList = list()
		isRunning = False
		house = None
		originalVoice = None
		
	elif message.content.startswith(">--test"):
		m = await message.channel.send("Hi")
		await m.add_reaction("Stonks")
			
	return
			
			
@client.event
async def on_reaction_add(reaction, member):
	if member == client.user or isRunning == False:
		return
		
	player = findPlayer(member)
	
	if reaction.emoji == "\u2B06":
		await switchRoom(player, player.room.neighbors[0], reaction.message)
		
	elif reaction.emoji == "\u2B07":
		await switchRoom(player, player.room.neighbors[1], reaction.message)
		
	elif reaction.emoji == "\u2B05":
		await switchRoom(player, player.room.neighbors[2], reaction.message)
		
	elif reaction.emoji == "\u27A1":
		await switchRoom(player, player.room.neighbors[3], reaction.message)
		
	elif reaction.emoji == "\u2934":
		await switchRoom(player, player.room.neighbors[4], reaction.message)
		
	elif reaction.emoji == "\u2935":
		await switchRoom(player, player.room.neighbors[5], reaction.message)
		
	return
		

@client.event
async def on_reaction_remove(reaction, member):
	if member == client.user or isRunning == False:
		return
		
	player = findPlayer(member)
	player.isMoving = False
		

def findPlayer(member):
	global playerList

	for p in playerList:
		if p.member == member:
			return p
			
			
			
def getPlayerWithNumber(number):
	global playerList
	
	for p in playerList:
		if p.number == number:
			return p
			
			

def getNavEmbed(room):
	e = discord.Embed()
	e.title = room.name
	e.description = "Click on the reactions below this message to navigate to other rooms!"
	e.colour = 0x880000
	
	if room.neighbors[0] is not None:
		e.add_field(name="========================", value=":arrow_up: : **" + room.neighbors[0].name + "**", inline=False)
		
	if room.neighbors[1] is not None:
		e.add_field(name="========================", value=":arrow_down: : **" + room.neighbors[1].name + "**", inline=False)
		
	if room.neighbors[2] is not None:
		e.add_field(name="========================", value=":arrow_left: : **" + room.neighbors[2].name + "**", inline=False)
		
	if room.neighbors[3] is not None:
		e.add_field(name="========================", value=":arrow_right: : **" + room.neighbors[3].name + "**", inline=False)
		
	if room.neighbors[4] is not None:
		e.add_field(name="========================", value=":arrow_heading_up: : **" + room.neighbors[4].name + "**", inline=False)
		
	if room.neighbors[5] is not None:
		e.add_field(name="========================", value=":arrow_heading_down: : **" + room.neighbors[5].name + "**", inline=False)
	
	
	return e
	
def getJobEmbed(job):
	e = discord.Embed()

	if job == "Murderer":
		e.title = "YOU ARE THE MURDERER"
		e.description = "Your goal is to kill all the innocents. Use command `stab <player number>` to stab someone in the same room as you. Others in that room will only see that someone was murdered, but a body gets left behind."
		e.colour = 0xAB0000
		
	if job == "Sheriff":
		e.title = "YOU ARE THE SHERIFF"
		e.description = "Your goal is to kill the murderers (if there's multiple) and try not to kill the other innocents. Use command `shoot <player number>` to shoot someone in the same room as you. Be careful, as shooting an innocent will make you unable to shoot for 45 seconds."
		e.colour = 0x1D67FF
	
	if job == "Innocent":
		e.title = "YOU ARE INNOCENT"
		e.description = "Your goal is to stay alive as long as possible. Dying is bad for your health, you know!"
		e.colour = 0x1D67C2
	
	return e
	
	
async def addNavReactions(message, room):
	if room.neighbors[0] is not None:
		await message.add_reaction("\u2B06")
		
	if room.neighbors[1] is not None:
		await message.add_reaction("\u2B07")
		
	if room.neighbors[2] is not None:
		await message.add_reaction("\u2B05")
		
	if room.neighbors[3] is not None:
		await message.add_reaction("\u27A1")
		
	if room.neighbors[4] is not None:
		await message.add_reaction("\u2934") 
		
	if room.neighbors[5] is not None:
		await message.add_reaction("\u2935")
		
	return
		
		
async def switchRoom(player, room, originalMessage):
	player.isMoving = True

	# Countdown to move
	moveCountdown = discord.Embed()
	moveCountdown.title = "Moving to " + room.name + " in 3....."
	moveCountdown.description = "Taking the express train to the " + room.name + "!"
	moveCountdown.colour = 0x21468A
	
	m = await player.tc.send(embed=moveCountdown)
	
	if player.isMoving == True:
		await asyncio.sleep(1)
		
	else:
		await m.delete()
		
	if player.isMoving == True:
		moveCountdown.title = "Moving to " + room.name + " in 3..... 2....."
		await m.edit(embed=moveCountdown)
		await asyncio.sleep(1)
		
	else:
		await m.delete()
		
	if player.isMoving == True:
		moveCountdown.title = "Moving to " + room.name + " in 3..... 2..... 1....."
		await m.edit(embed=moveCountdown)
		await asyncio.sleep(1)
		
	else:
		await m.delete()

	if player.isMoving == True:
		# Remove previous room's navigation
		await originalMessage.delete()
		await m.delete()

		# Give the player the new room role
		await player.member.add_roles(room.role)
		
		await player.member.move_to(room.vc)
		player.room.players.remove(player)
		room.players.append(player)
		
		await player.member.remove_roles(player.room.role)
		
		moveInfo = discord.Embed()
		moveInfo.title = player.member.display_name + " went to " + room.name
		moveInfo.description = "They'll miss you!"
		moveInfo.colour = 0x3474EB
		
		# Notify the players in the previous room where this player went
		for p in player.room.players:
			if p.member != player.member:
				await p.tc.send(embed=moveInfo, delete_after=10.0)
			
		player.room = room
		
		if len(room.items) > 1:
			await player.tc.send(embed=room.getRoomStatus())
		
		# Display the new room navigation for the player
		msg = await player.tc.send(embed=getNavEmbed(room))
		await addNavReactions(msg, room)
		
	else:
		await m.delete()
	
	return
		
	
async def moveToDeadChat(player, killer):
	global house

	await player.tc.purge(limit=20, bulk=True)
	vNotify = discord.Embed()
	vNotify.title = "You have been killed by the " + killer.job + "! Moving to Dead chat in 3....."
	vNotify.description = "RIP"
	vNotify.colour = 0xC20000
	
	m = await player.tc.send(embed=vNotify)
	await asyncio.sleep(1)
	
	vNotify.title = "You have been murdered by the " + killer.job + "! Moving to Dead chat in 3..... 2....."
	await m.edit(embed=vNotify)
	await asyncio.sleep(1)
	
	vNotify.title = "You have been murdered by the " + killer.job + "! Moving to Dead chat in 3..... 2..... 1....."
	await m.edit(embed=vNotify)
	await asyncio.sleep(1)
	
	await m.delete()
	
	player.room.items.append(("Body", player))
	
	if player.job == "Sheriff":
		player.room.items.append(("Gun", "Gun"))
	
	player.room.players.remove(player)
	house.rooms[len(house.rooms) - 1].players.append(player)
	
	await player.member.add_roles(house.rooms[len(house.rooms) - 1].role)
	await player.member.move_to(house.rooms[len(house.rooms) - 1].vc)
	await player.member.remove_roles(player.room.role)
	
	for p in player.room.players:
		await p.tc.send(embed=player.room.getRoomStatus())
		
	player.room = house.rooms[len(house.rooms) - 1]
	
	return
	

class Player:
	def __init__(self, member, number, tc, team, job, room):
		self.member = member
		self.tc = tc
		self.number = number
		self.room = room
		self.team = team
		self.job = job
		self.gunEligible = True
		self.roomStatMessage = None
		
		self.dead = False
		self.isMoving = False
		
	def __lt__(self, other):
		return self.number < other.number
		
	def __le__(self, other):
		return self.number <= other.number
	
	def __eq__(self, other):
		return self.number == other.number
		
	def __ne__(self, other):
		return self.number != other.number
		
	def __gt__(self, other):
		return self.number > other.number
		
	def __ge__(self, other):
		return self.number >= other.number
		

class Room:
	def __init__(self, name):
		self.name = name
		self.items = list()
		self.items.append(("Bop", "Boop"))
		self.neighbors = list()
		self.players = list()
		
	def setNeighbors(self, neighbors):
		self.neighbors = neighbors
		
	def setVC(self, channel):
		self.vc = channel
		
	def setRole(self, role):
		self.role = role
		
	def addItem(self, item):
		self.items.append(item)
		
	def getRoomStatus(self):
		e = discord.Embed()
		e.title = self.name + " Items"
		e.description = "Every item of interest in this room:"
		e.colour = 0xEDC31C
		
		for i in range(0, len(self.items)):
			if self.items[i][0] == "Body":
				e.add_field(name="========================", value=("**" + str(i) + ":** " + self.items[i][1].member.display_name + "\'s Body -- Use `check " + str(i) + "` to see what their role was!"), inline=False)
				
			if self.items[i][0] == "Gun":
				e.add_field(name="========================", value=("**" + str(i) + ":** " + self.items[i][0] + "! The sheriff must have dropped it. Use `get " + str(i) + "` to pick up the gun (if you\'re eligible)!"), inline=False)
				
		return e
		
		
class House:
	def __init__(self, name, number):
		self.name = name
		
		# Construct a house from rooms (temporary hard-code)
		if number == 1:
			foyer = Room("Foyer")
			diningRoom = Room("Dining Room")
			livingRoom = Room("Living Room")
			recRoom = Room("Rec Room")
			northwestHall = Room("Northwest Hall")
			northeastHall = Room("Northeast Hall")
			
			foyerNeighbors = [diningRoom, None, livingRoom, recRoom, None, None]
			diningRoomNeighbors = [None, foyer, northwestHall, northeastHall, None, None]
			livingRoomNeighbors = [northwestHall, None, None, foyer, None, None]
			recRoomNeighbors = [northeastHall, None, foyer, None, None, None]
			northwestHallNeighbors = [None, livingRoom, None, diningRoom, None, None]
			northeastHallNeighbors = [None, recRoom, diningRoom, None, None, None]
			
			foyer.setNeighbors(foyerNeighbors)
			diningRoom.setNeighbors(diningRoomNeighbors)
			livingRoom.setNeighbors(livingRoomNeighbors)
			recRoom.setNeighbors(recRoomNeighbors)
			northwestHall.setNeighbors(northwestHallNeighbors)
			northeastHall.setNeighbors(northeastHallNeighbors)
			
			self.rooms = [foyer, diningRoom, livingRoom, recRoom, northwestHall, northeastHall]
			
		elif number == 2:
			foyer = Room("Foyer")
			diningRoom = Room("Dining Room")
			livingRoom = Room("Living Room")
			recRoom = Room("Rec Room")
			northwestHall = Room("Northwest Hall")
			northeastHall = Room("Northeast Hall")
			upstairsHall = Room("Upstairs Hall")
			masterBedroom = Room("Master Bedroom")
			balcony = Room("Balcony")
			homeOffice = Room("Home Office")
			guestBedroom = Room("Guest Bedroom")
			
			foyerNeighbors = [diningRoom, None, livingRoom, recRoom, None, None]
			diningRoomNeighbors = [None, foyer, northwestHall, northeastHall, None, None]
			livingRoomNeighbors = [northwestHall, None, None, foyer, None, None]
			recRoomNeighbors = [northeastHall, None, foyer, None, None, None]
			northwestHallNeighbors = [None, livingRoom, None, diningRoom, None, None]
			northeastHallNeighbors = [None, recRoom, diningRoom, None, upstairsHall, None]
			upstairsHallNeighbors = [None, guestBedroom, masterBedroom, None, None, northeastHall]
			masterBedroomNeighbors = [None, balcony, homeOffice, upstairsHall, None, None]
			balconyNeighbors = [masterBedroom, None, None, None, None, None]
			homeOfficeNeighbors = [None, None, None, masterBedroom, None, None]
			guestBedroomNeighbors = [upstairsHall, None, None, None, None, None]
			
			foyer.setNeighbors(foyerNeighbors)
			diningRoom.setNeighbors(diningRoomNeighbors)
			livingRoom.setNeighbors(livingRoomNeighbors)
			recRoom.setNeighbors(recRoomNeighbors)
			northwestHall.setNeighbors(northwestHallNeighbors)
			northeastHall.setNeighbors(northeastHallNeighbors)
			upstairsHall.setNeighbors(upstairsHallNeighbors)
			masterBedroom.setNeighbors(masterBedroomNeighbors)
			balcony.setNeighbors(balconyNeighbors)
			homeOffice.setNeighbors(homeOfficeNeighbors)
			guestBedroom.setNeighbors(guestBedroomNeighbors)
			
			self.rooms = [foyer, diningRoom, livingRoom, recRoom, northwestHall, northeastHall, upstairsHall, masterBedroom, balcony, homeOffice, guestBedroom]
		

client.run(TOKEN)