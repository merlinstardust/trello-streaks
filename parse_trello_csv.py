import json
import os
import sys
import re
from datetime import datetime, timedelta
from trello.client import TrelloClient


TRELLO_CREDS = json.loads(os.getenv('TRELLO_CREDS'))
TC = TrelloClient(**TRELLO_CREDS)
ME = TC.get_member('me')
NOW = datetime.now()
TOMORROW = NOW + timedelta(days=1, minutes=-1)
WEEKDAYS = ['Every day', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
YEAR, MONTH, DAY, WDAY, HOUR = NOW.year, NOW.month, NOW.day, NOW.isoweekday(), NOW.hour


def parse_days(days):
    if days == '0':
        return set(range(1, 8))

    days_split = days.split(';')
    days = set()
    for day in days_split:
        if '-' in day:
            start, end = day.split('-')
            days |= set(range(int(start), int(end) + 1))
        else:
            days.add(int(day))

    return days


def parse_checklists(line):
    if type(line) is str:
        line = line.split(',')

    start = 2
    end = start + int(line[1])
    checklists_unparsed = line[start:end]
    
    checklists = {}
    for checklist in checklists_unparsed:
        if '=' in checklist:
            name, checklist = checklist.split('=')
        else:
            name = 'Checklist'
        checklists[name] = checklist.split(';')

    return checklists


def parse_task(line):
    line = line.split(',')

    task = line[0]

    if len(line) > 1:
        checklists = parse_checklists(line)
        options = line[2 + int(line[1]):]
    else:
        checklists = None
        options = None

    return task, checklists, options


def count(action, kind, card):
    match = re.search('%s=(\d*)' % kind, card.name)
    count = int(match.group(1)) if match else 0
    if action == 'inc':
        count += 1
    count_str = ' (%s=%s)' % (kind, count)
    return count_str, count


def parse_trello_csv(filename):
    lines = []
    cards = []
    with open(filename) as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if 'board=' in line:
            board = line.split('=')[1]
            board = TC.search_boards(board)
            print 'Tasks for %s' % board
            continue
        
        if 'list=' in line:
            tlist = line.split('=')[1]
            tlist = board.search_lists(tlist)
            print ' on %s' % tlist
            continue

        if 'days=' in line:
            days = parse_days(line.split('=')[1])
            wdays = [WEEKDAYS[day] for day in days]
            if WDAY in days:
                wdays[wdays.index(WEEKDAYS[WDAY])] += '*'
            print ' for days %s' % wdays
            continue

        task, checklists, options = parse_task(line)

        print '  task = %s' % task
        if checklists:
            print '  checklists'
            for name, checklist in checklists.iteritems():
                print '   %s' % name
                for item in checklist:
                    print '    %s' % item
        if options:
            print '  options'
            for option in options:
                print '   %s' % option
        print ''

        if WDAY in days:
            old_card = tlist.search_cards(task)
            counts = ''

            # card was still in list so task was missed
            if old_card and type(old_card) is not list:
                missed_str, missed = count('inc', 'missed', old_card)
                last_streak_str, last_streak = count('get', 'lastStreak', old_card)
                if not last_streak:
                    streak_str, streak = count('get', 'streak', old_card)
                    last_streak_str = ' (lastStreak=%s)' % (streak) if streak else ''
                counts = '%s%s' % (missed_str, last_streak_str)
                print 'Deleted old_card %s' % old_card
                old_card.delete()
            
            # card was archived so task was completed
            elif not old_card:
                old_cards = tlist.search_cards(task, 'closed')
                if old_cards:
                    if type(old_cards) == list:
                        old_card = old_cards[0]
                    else:
                        old_card = old_cards
                    streak_str, streak = count('inc', 'streak', old_card)
                    counts = streak_str

            card = tlist.add_card('%s - %s%s' % (NOW.date(), task, counts))
            card.assign(ME.id)
            card.set_due(TOMORROW)
            if checklists:
                for name, checklist in checklists.iteritems():
                    card.add_checklist(name, checklist)
            print 'Added card "%s"' % task
            cards.append(card)


if __name__ == '__main__':
    script_name = sys.argv[0]
    trello_filename = sys.argv[1]

    print 'date=%s, wday=%s, hour=%s' % (NOW.date(), WEEKDAYS[WDAY], HOUR)
    print 'me=%s' % ME

    parse_trello_csv(trello_filename)
