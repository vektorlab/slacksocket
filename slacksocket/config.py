slack = 'https://slack.com/api/'

urls = { 'test': slack + 'auth.test',
         'rtm': slack + 'rtm.start',
         'users': slack + 'users.list',
         'im.open': slack + 'im.open',
         'convos': slack + 'conversations.list' }

# event types as given in https://api.slack.com/events
event_types = [ 'hello',
                'message',
                'channel_marked',
                'channel_created',
                'channel_joined',
                'channel_left',
                'channel_deleted',
                'channel_rename',
                'channel_archive',
                'channel_unarchive',
                'channel_history_changed',
                'im_created',
                'im_open',
                'im_close',
                'im_marked',
                'im_history_changed',
                'group_joined',
                'group_left',
                'group_open',
                'group_close',
                'group_archive',
                'group_unarchive',
                'group_rename',
                'group_marked',
                'group_history_changed',
                'file_created',
                'file_shared',
                'file_unshared',
                'file_public',
                'file_private',
                'file_change',
                'file_deleted',
                'file_comment_added',
                'file_comment_edited',
                'file_comment_deleted',
                'presence_change',
                'manual_presence_change',
                'pref_change',
                'user_change',
                'team_join',
                'star_added',
                'star_removed',
                'emoji_changed',
                'commands_changed',
                'team_pref_change',
                'team_rename',
                'team_domain_change',
                'email_domain_changed',
                'bot_added',
                'bot_changed',
                'accounts_changed',
                'user_typing',
                'team_migration_started' ]

def validate_filters(self, filters):
    if filters == 'all':
        return

    if type(filters) != list:
        raise TypeError('filters must be given as a list')

    invalid = [ f for f in filters if f not in event_types ]
    if invalid:
        raise errors.ConfigError('unknown event types: %s\n \
                     see https://api.slack.com/events' % filters)
