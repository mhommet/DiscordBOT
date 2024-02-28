from random import choice, randint

def get_response(user_input: str) -> str:
    lowered: str = user_input.lower()

    if lowered == '':
        return 'Well, you are silent'
    elif 'roll' in lowered:
        return f'You rolled a {randint(1, 6)}'
    else:
        return choice(['I do not undertsand', 'What?', 'I am a bot, not a human'])
