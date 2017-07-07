"""sqlalchemy table and ORM definitions for Agora."""

from sqlalchemy import create_engine, create_session, BoundMetaData, \
                       Table, mapper, relation, func

DATABASE_URL = 'postgres://agora@localhost/agora'

engine = create_engine(DATABASE_URL)
session = create_session(bind_to=engine)
metadata = BoundMetaData(engine)

_entity = Table('entity', metadata, autoload=True)
_player = Table('player', metadata, autoload=True)

class DbObject(object):
    def __repr__(self):
        return '(%s: %s)' % (type(self),
                             ', '.join('%s=%s' % (x, getattr(self, x)) \
                                       for x in self.c.keys()))

class Entity(DbObject):
    pass

class Player(DbObject):
    def get_name(self):
        return self.entity.name
    def set_name(self, name):
        self.entity.name = name
    name = property(get_name, set_name)

    def get_short(self):
        return self.entity.short
    def set_short(self, short):
        self.entity.short = short
    short = property(get_short, set_short)


mapper(Entity, _entity)

mapper(Player, _player,
       properties = {'entity': relation(Entity, lazy=False,
                                        cascade="all, delete-orphan")})


def get_players(all=False):
    if all:
        return session.query(Player).select()
    else:
        return session.query(Player).select_by(current=True)


def get_player(name):
    name = name.lower()
    query = session.query(Entity)

    entity = query.get_by(func.lower(Entity.c.name) == name)
    if entity is None:
        entity = query.get_by(func.lower(Entity.c.short) == name)

    if entity:
        return session.query(Player).get_by(entity=entity)
