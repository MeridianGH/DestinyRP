import os
import sys
from dotenv import load_dotenv  # python-dotenv
import pydest
import pypresence
import asyncio
import nest_asyncio  # nest-asyncio
import yaml  # PyYaml


if hasattr(sys, '_MEIPASS'):
    path = '/'.join(sys.executable.split('\\')[0:-1])
else:
    path = '/'.join(__file__.split('/')[0:-1])
try:
    config = yaml.safe_load(open(path + '/config.yml', encoding='utf8'))
except FileNotFoundError or Exception:
    print(f'Please place a valid config.yml in this directory: {path}')
    input()
    raise Exception('No config provided!')


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(relative_path)


load_dotenv(dotenv_path=resource_path('./venv/.env'))
api_key = os.getenv('API_KEY')
client_id = os.getenv('CLIENT_ID')
headers = {"X-API-Key": api_key}

platforms = {'All': -1, 'PS4': 1, 'XBox': 2, 'Steam': 3}

loop = asyncio.ProactorEventLoop()
nest_asyncio.apply(loop)
asyncio.set_event_loop(loop)
rpc = pypresence.Presence(client_id)


async def get_info(username, platform):
    destiny = pydest.Pydest(api_key)
    try:
        platform = platforms[platform]
    except KeyError:
        platform = -1
    user = await destiny.api.search_destiny_player(platform, username)
    if user['Response']:
        # print('Found player \'' + user.get('Response')[0].get('displayName') + '\'!')
        info = await destiny.api.get_profile(membership_type=user.get('Response')[0].get('membershipType'),
                                             membership_id=user.get('Response')[0].get('membershipId'),
                                             components=['characterActivities'])
        if info['Response']:
            data = info.get('Response').get('characterActivities').get('data')
            for index, character in enumerate(data):
                if data.get(character).get('currentActivityHash') != 0:
                    await destiny.update_manifest()
                    try:
                        activity_hash = abs(int(data.get(character).get('currentActivityHash')))
                        activity = await destiny.decode_hash(activity_hash, 'DestinyActivityDefinition')
                        if activity.get('displayProperties').get('name') is None:
                            await destiny.close()
                            return activity, {'displayProperties': {'name': 'Orbit'}}

                        mode_hash = abs(int(data.get(character).get('currentActivityModeHash')))
                        try:
                            mode = await destiny.decode_hash(mode_hash, 'DestinyActivityModeDefinition')
                        except pydest.PydestException or Exception:
                            await destiny.close()
                            return activity, {'displayProperties': {'name': 'Activity'}}
                        await destiny.close()
                        return activity, mode
                    except pydest.PydestException or Exception as e:
                        print(f'Failed to fetch data for Character {index + 1}!')
                        print(e)
                        return

                elif data.get(character).get('currentActivityHash') == 0:
                    print(f'Character {index + 1} is not playing Destiny 2!')
                else:
                    print(f'Failed to fetch data for Character {index + 1}!')
        elif info['Response'] == [] and info['ErrorStatus'] == 'Success':
            print('Could not fetch data for user \'' + user.get('Response')[0].get('displayName') + '\'!')
        else:
            print(info['ErrorStatus'])
    elif user['Response'] == [] and user['ErrorStatus'] == 'Success':
        print(f'Could not find user \'{username}\' on platform \'{platform}\'.')
    else:
        print(user['ErrorStatus'])
    await destiny.close()


async def set_presence(activity, mode):
    activity, mode, image = parse_activity(activity, mode)
    print(mode)
    print(activity)
    if mode is None:
        rpc.update(state='Launching game...', large_image='main', large_text='Starting D2 RPC')
    else:
        rpc.update(details=mode, state=activity,
                   large_image=image['asset'], large_text=image['text'])


def parse_activity(activity, mode):
    if mode is None or activity is None:
        return None, None, None
    else:
        mode_name = mode.get('displayProperties').get('name')
        activity_name = activity.get('displayProperties').get('name')
        image = {'asset': 'name', 'text': 'text'}
        # Free Roam
        if mode_name == 'Explore':
            if activity_name == 'Landing Zone':
                activity_name = 'Mercury: Fields of Glass'
            elif activity_name == 'Io':
                activity_name = 'Io: Echo Mesa'
            elif activity_name == 'Hellas Basin':
                activity_name = 'Mars: Hellas Basin'
            elif activity_name == 'Titan':
                activity_name = 'Titan: New PacificArcology'
            elif activity_name == 'Nessus, Unstable Centaur':
                activity_name = 'Nessus: Arcadian Valley'
            elif activity_name == 'The Moon':
                activity_name = 'The Moon'
            elif activity_name == 'The Dreaming City':
                activity_name = 'The Dreaming City'
            elif activity_name == 'The Tangled Shore':
                activity_name = 'The Tangled Shore'
            else:
                # Adventures and other Activities
                if activity_name == 'The Tribute Hall':
                    mode_name = 'In the Tribute Hall'
                    activity_name = None
                    image = {'asset': 'exploring', 'text': 'In the Tribute Hall'}
                else:
                    mode_name = 'Playing: Adventure'
                    image = {'asset': 'exploring', 'text': 'Exploring'}
                return activity_name, mode_name, image
            mode_name = 'Exploring:'
            image = {'asset': 'exploring', 'text': 'Exploring'}
        # Story
        elif mode_name == 'Story':
            # Dungeons
            if activity_name == 'The Shattered Throne' or activity_name == 'Pit of Heresy':
                mode_name = 'Playing: Dungeon'
                image = {'asset': 'nightmarehunt', 'text': mode_name}
            else:
                mode_name = 'Playing: Story'
                image = {'asset': 'story', 'text': mode_name}
        # Strikes
        elif mode_name == 'Normal Strikes':
            mode_name = 'Playing: Vanguard Strike'
            image = {'asset': 'gambit', 'text': mode_name}
        elif mode_name == 'Scored Nightfall Strikes':
            if 'The Ordeal' in activity_name:
                mode_name = 'Nightfall: The Ordeal'
                activity_name = activity.get('displayProperties').get('description') + ' - ' + \
                    activity_name.replace('Nightfall: The Ordeal: ', '')
            else:
                mode_name = 'Playing: Nightfall Strike'
                activity_name = activity_name.replace('Nightfall: ', '')
            image = {'asset': 'nightfall', 'text': mode_name}
        # Gambit
        elif mode_name == 'Gambit' or mode_name == 'Gambit Prime' or mode_name == 'The Reckoning':
            mode_name = 'Playing: ' + mode_name
            image = {'asset': 'gambit', 'text': mode_name}
        # Crucible
        elif mode.get('pgcrImage') == '/img/theme/destiny/bgs/stats/banner_crucible_1.jpg':
            if 'Iron Banner' in mode_name:
                mode_name = 'Playing Iron Banner: ' + mode_name.replace('Iron Banner ', '')
                image = {'asset': 'iron_banner', 'text': mode_name}
            else:
                mode_name = 'Playing Crucible: ' + mode_name
                image = {'asset': 'crucible', 'text': mode_name}
        # Menagerie
        elif mode_name == 'The Menagerie':
            mode_name = 'Playing: Menagerie'
            activity_name = activity_name.replace('The Menagerie: ', '')
            image = {'asset': 'menagerie', 'text': mode_name}
        elif mode_name == 'Raid':
            mode_name = 'Playing: Raid'
            image = {'asset': 'raid', 'text': mode_name}
        elif mode_name == 'Activity':
            if activity_name.startswith('Nightmare Hunt:'):
                mode_name = 'Playing: Nightmare Hunt'
                activity_name = activity_name.replace('Nightmare Hunt: ', '')
                image = {'asset': 'nightmare_hunt', 'text': mode_name}
            elif activity_name == 'Vex Offensive':
                mode_name = 'Playing: Vex Offensive'
                image = {'asset': 'vex_offensive', 'text': 'Playing: Vex Offensive'}
        # Tower and Orbit
        elif mode_name == 'Social':
            mode_name = 'In the Tower'
            activity_name = None
            image = {'asset': 'tower', 'text': 'In the Tower'}
        elif mode_name == 'Orbit':
            mode_name = 'In Orbit'
            activity_name = None
            image = {'asset': 'main', 'text': 'In Orbit'}
        return activity_name, mode_name, image


async def main(username, platform):
    rpc.connect()
    await set_presence(None, None)
    while True:
        activity, mode = await get_info(username, platform)
        await asyncio.sleep(7)
        await set_presence(activity, mode)
        await asyncio.sleep(8)


if __name__ == '__main__':
    loop.create_task(main(config['username'], config['platform']))
    loop.run_forever()
