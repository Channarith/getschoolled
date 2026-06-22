// Teams <-> LiveKit media bridge sidecar (phase 8) - HTTP control plane.
//
// Exposes exactly the control-plane contract that the Python bridge's
// HttpSidecarTransport calls (aoep_shared/bridges/platforms.py):
//
//   POST /call/join     {threadId, tenantId, livekitUrl, livekitRoom, livekitToken}
//   POST /call/bridge   {kind, direction}
//   POST /call/announce {text, recording}
//   POST /call/chat     {text}
//   POST /call/leave    {}
//
// The platform-agnostic policy (which tracks, disclosures, chat routing) is
// decided by the Python engine; this service performs the Graph Communications
// media work for each command. Requires an Azure bot registration + media
// platform certificate to run live (see appsettings.json).

using Aoep.Bridges.Teams;

var builder = WebApplication.CreateBuilder(args);
builder.Services.Configure<TeamsBridgeOptions>(builder.Configuration.GetSection("TeamsBridge"));
builder.Services.AddSingleton<TeamsCallingBridge>();
var app = builder.Build();

var bridge = app.Services.GetRequiredService<TeamsCallingBridge>();

app.MapGet("/health", () => Results.Ok(new { status = "ok", service = "aoep-teams-bridge" }));

app.MapPost("/call/join", async (JoinRequest req) =>
{
    await bridge.JoinAsync(req);
    return Results.Ok(new { joined = true, threadId = req.ThreadId });
});

app.MapPost("/call/bridge", async (BridgeTrackRequest req) =>
{
    await bridge.BridgeTrackAsync(req.Kind, req.Direction);
    return Results.Ok(new { bridged = true, req.Kind, req.Direction });
});

app.MapPost("/call/announce", async (AnnounceRequest req) =>
{
    await bridge.AnnounceAsync(req.Text, req.Recording);
    return Results.Ok(new { announced = true });
});

app.MapPost("/call/chat", async (ChatRequest req) =>
{
    await bridge.SendChatAsync(req.Text);
    return Results.Ok(new { sent = true });
});

app.MapPost("/call/leave", async () =>
{
    await bridge.LeaveAsync();
    return Results.Ok(new { left = true });
});

app.Run();

// Control-plane DTOs (mirror the Python HttpSidecarTransport payloads).
public record JoinRequest(string ThreadId, string? TenantId, string LivekitUrl, string LivekitRoom, string LivekitToken);
public record BridgeTrackRequest(string Kind, string Direction);
public record AnnounceRequest(string Text, bool Recording);
public record ChatRequest(string Text);
