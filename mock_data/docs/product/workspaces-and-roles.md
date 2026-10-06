# Workspaces, roles, and permissions

Permissions are assigned at the workspace level. A user can belong to more than one workspace and have a different role in each.

## Roles

| Action | Owner | Admin | Member | Viewer |
| --- | --- | --- | --- | --- |
| View projects and tasks | Yes | Yes | Yes | Yes |
| Create and edit tasks | Yes | Yes | Yes | No |
| Create projects | Yes | Yes | Yes | No |
| Invite members | Yes | Yes | No | No |
| Manage roles | Yes | Yes, except Owner | No | No |
| Change billing details | Yes | No | No | No |
| Delete workspace | Yes | No | No | No |

## Change a role

An Owner or Admin can open **Settings > Members**, select a member, and choose a new role. Admins cannot grant or remove the Owner role. A workspace must always have exactly one Owner. To transfer ownership, the current Owner uses **Settings > Workspace > Transfer ownership**.

## Project visibility

All workspace members can view all projects in that workspace. HarborDesk does not currently offer private projects. Do not put confidential project details in a workspace whose Viewers should not see them.
