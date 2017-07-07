#!/usr/bin/python

"""Functions to manage the list of Agora players in the database."""


from optparse import OptionParser
import agora


def add_player(name, short=None):
    session = agora.session
    player = agora.get_player(name)

    if not player:
        entity = agora.Entity()
        entity.name = name
        session.save(entity)

        player = agora.Player()
        player.entity = entity
        session.save(player)

    player.current = True
    if short:
        player.short = short

    session.flush()


def delete_player(name):
    session = agora.session
    player = agora.get_player(name)
    if player:
        player.current = False
        session.flush()


def rename_player(old, new, short=None):
    session = agora.session
    player = agora.get_player(old)
    if player:
        player.name = new
        player.short = short
        session.flush()


def list_players():
    players = agora.get_players()
    players.sort(key=lambda x:x.name.lower())

    for player in players:
        if player.short:
            print '%s (%s)' % (player.name, player.short)
        else:
            print player.name


def main():
    usage = "usage: %prog [options] {add|del} NAME\n" \
            "       %prog [options] rename OLD NEW\n" \
            "       %prog list"

    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--short", dest="short",
                      help="abbreviate player name as SHORT", metavar="SHORT")

    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.print_help()
        return

    command = args[0].lower()
    if command == 'add' and len(args) >= 2:
        add_player(args[1], options.short)
    elif command == 'del' and len(args) >= 2:
        delete_player(args[1])
    elif command == 'rename' and len(args) >= 3:
        rename_player(args[1], args[2], options.short)
    elif command == 'list':
        list_players()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()