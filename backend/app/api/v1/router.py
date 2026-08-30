from fastapi import APIRouter

from app.api.v1 import (
    ai,
    approvals,
    assets,
    auth,
    billing,
    campaigns,
    data_sources,
    decisioning,
    deployments,
    developer,
    devices,
    edge,
    events,
    experiments,
    health,
    integrations,
    layouts,
    locations,
    notification_rules,
    ops,
    organization,
    platform,
    player,
    playlists,
    releases,
    roles,
    search,
    storage_local,
    studio,
    users,
    video_walls,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(roles.router, tags=["roles"])
api_router.include_router(organization.router, tags=["organization"])
api_router.include_router(locations.router, tags=["locations"])
api_router.include_router(assets.router, tags=["content"])
api_router.include_router(storage_local.router, tags=["storage"])
api_router.include_router(devices.router, tags=["devices"])
api_router.include_router(player.router, tags=["player"])
api_router.include_router(layouts.router, tags=["layouts"])
api_router.include_router(playlists.router, tags=["playlists"])
api_router.include_router(campaigns.router, tags=["campaigns"])
api_router.include_router(deployments.router, tags=["deployments"])
api_router.include_router(ops.router, tags=["operations"])
api_router.include_router(approvals.router, tags=["approvals"])
api_router.include_router(releases.router, tags=["releases"])
api_router.include_router(studio.router, tags=["studio"])
api_router.include_router(notification_rules.router, tags=["notification-rules"])
api_router.include_router(integrations.router, tags=["integrations"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(billing.router, tags=["billing"])
api_router.include_router(platform.router, tags=["platform"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(data_sources.router, tags=["data-sources"])
api_router.include_router(developer.router, tags=["developer"])
api_router.include_router(ai.router, tags=["ai"])
api_router.include_router(decisioning.router, tags=["decisioning"])
api_router.include_router(experiments.router, tags=["experiments"])
api_router.include_router(video_walls.router, tags=["video-walls"])
api_router.include_router(edge.router, tags=["edge"])
