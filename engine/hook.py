'''
import nacl.signing
import nacl.exceptions

DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')  # Your application's public key

# Verify the request signature
async def verify_signature(request):
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    body = await request.body()

    if not signature or not timestamp:
        return False

    try:
        verify_key = nacl.signing.VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except nacl.exceptions.BadSignatureError:
        return False

@app.post('/discord-webhook')
async def discord_webhook(request: Request):
    if not await verify_signature(request):
        return {"error": "Invalid request signature"}

    payload = await request.json()
    event_type = payload.get('type')

    if event_type == 'APPLICATION_COMMAND_CREATE':
        # Handle application command creation
        # Send a notification to a specific channel
        await handle_command_creation(payload)

    elif event_type == 'ENTITLEMENT_CREATE':
        # Handle new purchase or subscription
        await handle_entitlement_create(payload)

    elif event_type == 'ENTITLEMENT_DELETE':
        # Handle entitlement deletion (e.g., subscription canceled)
        await handle_entitlement_delete(payload)

    elif event_type == 'QUEST_PROGRESS':
        # Handle quest progress updates
        await handle_quest_progress(payload)

    # Add more event handlers as needed

    return {"status": "success"}

# Handler for APPLICATION_COMMAND_CREATE
async def handle_command_creation(payload):
    command_name = payload.get('data', {}).get('name', 'Unknown command')
    guild_id = payload.get('guild_id')
    channel_id = payload.get('channel_id')
    user_id = payload.get('member', {}).get('user', {}).get('id')
    if not user_id or not guild_id or not channel_id:
        return
    guild = bot.get_guild(int(guild_id))
    channel = guild.get_channel(int(channel_id))
    user = guild.get_member(int(user_id))
    if channel and user:
        await channel.send(f"🆕 {user.mention} created a new command: `{command_name}`")

# Handler for ENTITLEMENT_CREATE
async def handle_entitlement_create(payload):
    user_id = payload.get('user_id')
    if not user_id:
        return
    # Assuming the entitlement includes guild_id and role information
    guild_id = payload.get('guild_id')
    role_id = payload.get('role_id')  # The role to assign, provided in the payload
    if not guild_id or not role_id:
        return
    guild = bot.get_guild(int(guild_id))
    member = guild.get_member(int(user_id))
    premium_role = guild.get_role(int(role_id))
    if member and premium_role:
        await member.add_roles(premium_role)
        try:
            await member.send("🎉 Thank you for your purchase! You've been granted the Premium role.")
        except discord.Forbidden:
            pass  # The user has DMs closed

# Handler for ENTITLEMENT_DELETE
async def handle_entitlement_delete(payload):
    user_id = payload.get('user_id')
    if not user_id:
        return
    guild_id = payload.get('guild_id')
    role_id = payload.get('role_id')  # The role to remove, provided in the payload
    if not guild_id or not role_id:
        return
    guild = bot.get_guild(int(guild_id))
    member = guild.get_member(int(user_id))
    premium_role = guild.get_role(int(role_id))
    if member and premium_role:
        await member.remove_roles(premium_role)
        try:
            await member.send("⚠️ Your subscription has ended. The Premium role has been removed.")
        except discord.Forbidden:
            pass  # The user has DMs closed

# Handler for QUEST_PROGRESS
async def handle_quest_progress(payload):
    user_id = payload.get('user_id')
    guild_id = payload.get('guild_id')
    quest_id = payload.get('quest_id')
    progress = payload.get('progress')
    if not user_id or progress is None or not guild_id:
        return
    guild = bot.get_guild(int(guild_id))
    member = guild.get_member(int(user_id))
    if not member:
        return
    # You can define quest rewards per guild
    quest_rewards = await get_quest_rewards(guild_id, quest_id)
    if progress == 100:
        # Quest completed
        if quest_rewards:
            role_id = quest_rewards.get('role_id')
            if role_id:
                quest_role = guild.get_role(int(role_id))
                if quest_role:
                    await member.add_roles(quest_role)
        try:
            await member.send(f"🏆 Congratulations! You've completed quest `{quest_id}` and earned rewards!")
        except discord.Forbidden:
            pass
    else:
        # Update progress
        try:
            await member.send(f"📈 Your progress for quest `{quest_id}` is now at {progress}%.")
        except discord.Forbidden:
            pass

async def get_quest_rewards(guild_id, quest_id):
    # Implement your method to retrieve quest rewards per guild and quest
    # This could be from a database or configuration file
    # For now, let's return a dummy example
    return {
        'role_id': 'ROLE_ID_FOR_REWARD'
    }
'''