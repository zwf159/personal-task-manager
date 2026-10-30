from .common import actions,invoke


def configure(groups):
    sub=actions(groups,'projects','查看、创建和归档项目')
    listing=sub.add_parser('list');listing.set_defaults(handler=lambda store,s,a:store.projects())
    create=sub.add_parser('add');create.add_argument('name');create.add_argument('--description',default='');create.set_defaults(handler=lambda store,s,a:store.create_project({'name':a.name,'description':a.description}))
    rename=sub.add_parser('rename');rename.add_argument('id',type=int);rename.add_argument('name');rename.set_defaults(handler=lambda store,s,a:invoke(s,'PATCH',f'/api/projects/{a.id}',{'name':a.name}))
    for action,archived in [('archive',True),('restore',False)]:
        command=sub.add_parser(action);command.add_argument('id',type=int)
        command.set_defaults(archived=archived,handler=lambda store,s,a:invoke(s,'PATCH',f'/api/projects/{a.id}',{'archived':a.archived}))
