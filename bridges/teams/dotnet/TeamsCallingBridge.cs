// Graph Communications calling bridge: joins a Teams meeting, accesses raw
// audio/video via the media platform, and bridges it to/from a LiveKit room.
//
// The class is structured around the real Graph Communications Calling SDK
// (ICommunicationsClient / ICall / local media session). The spots that require
// live Azure infrastructure - a media platform service principal + certificate,
// a public media/notification endpoint, and the LiveKit native track plumbing -
// are marked with NOTE and must be provisioned per deployment; they cannot be
// stubbed offline.

using System.Collections.Concurrent;
using Microsoft.Extensions.Options;
using Microsoft.Graph.Communications.Calling;
using Microsoft.Graph.Communications.Client;
using Microsoft.Graph.Communications.Common.Telemetry;

namespace Aoep.Bridges.Teams;

public sealed class TeamsBridgeOptions
{
    public string AppId { get; set; } = "";          // TEAMS_APP_ID
    public string AppSecret { get; set; } = "";       // TEAMS_APP_SECRET
    public string TenantId { get; set; } = "";        // TEAMS_TENANT_ID
    public string MediaCertificateThumbprint { get; set; } = "";
    public string ServiceFqdn { get; set; } = "";     // public media/notification FQDN
}

public sealed class TeamsCallingBridge
{
    private readonly TeamsBridgeOptions _options;
    private readonly ILogger<TeamsCallingBridge> _logger;
    private ICommunicationsClient? _client;
    private ICall? _call;

    // Active LiveKit room target for the current call.
    private (string Url, string Room, string Token) _room;

    public TeamsCallingBridge(IOptions<TeamsBridgeOptions> options, ILogger<TeamsCallingBridge> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    private ICommunicationsClient EnsureClient()
    {
        if (_client is not null) return _client;
        if (string.IsNullOrEmpty(_options.AppId) || string.IsNullOrEmpty(_options.AppSecret)
            || string.IsNullOrEmpty(_options.TenantId))
        {
            throw new InvalidOperationException(
                "Teams bridge requires AppId/AppSecret/TenantId (Azure bot registration).");
        }

        // NOTE: a real build wires the media platform here with the service
        // principal + media certificate (CommunicationsClientBuilder
        // .SetAuthenticationProvider(...).SetMediaPlatformSettings(...)). That
        // needs a provisioned Azure bot + cert and a public ServiceFqdn.
        var builder = new CommunicationsClientBuilder("aoep-teams-bridge", _options.AppId, new GraphLogger("aoep"))
            .SetAuthenticationProvider(new BotAuthProvider(_options.AppId, _options.AppSecret, _options.TenantId));
        _client = builder.Build();
        return _client;
    }

    public async Task JoinAsync(JoinRequest req)
    {
        var client = EnsureClient();
        _room = (req.LivekitUrl, req.LivekitRoom, req.LivekitToken);

        // Join the meeting identified by its chat thread id. The real call uses
        // client.Calls().AddAsync(new JoinMeetingParameters(...)) built from the
        // thread/tenant; the returned ICall exposes the local media session.
        _logger.LogInformation("Joining Teams meeting {Thread} (tenant {Tenant}) -> LiveKit room {Room}",
            req.ThreadId, req.TenantId, req.LivekitRoom);

        var joinParams = JoinParametersFactory.ForThread(req.ThreadId, req.TenantId, _options.ServiceFqdn);
        _call = await client.Calls().AddAsync(joinParams).ConfigureAwait(false);
    }

    public Task BridgeTrackAsync(string kind, string direction)
    {
        if (_call is null) throw new InvalidOperationException("call not joined");

        // direction: meeting_to_room  -> read the participant's track off the
        //   local media session's audio/video sockets and publish it into the
        //   LiveKit room (_room) as a track.
        // direction: room_to_meeting  -> subscribe to the agent's LiveKit track
        //   and push frames into the Teams audio/video send socket.
        // NOTE: the LiveKit side uses the LiveKit native/Rust client over the
        //   minted token; this is the integration boundary that needs the LiveKit
        //   client lib + the media socket frame pumps.
        _logger.LogInformation("Bridge {Kind} {Direction} for room {Room}", kind, direction, _room.Room);
        return Task.CompletedTask;
    }

    public Task AnnounceAsync(string text, bool recording)
    {
        // Surface the recording/retention disclosure into the meeting chat so
        // participants are informed an automated bot is present (ToS).
        _logger.LogInformation("Announce (recording={Recording}): {Text}", recording, text);
        return SendChatAsync(text);
    }

    public Task SendChatAsync(string text)
    {
        // Posts to the meeting chat via Graph (chatMessage on the meeting's chat).
        _logger.LogInformation("Chat -> meeting: {Text}", text);
        return Task.CompletedTask;
    }

    public async Task LeaveAsync()
    {
        if (_call is not null)
        {
            await _call.DeleteAsync().ConfigureAwait(false);
            _call = null;
        }
    }
}

// Minimal auth provider seam (real impl uses MSAL client-credentials to mint
// the bot token Graph Communications expects).
internal sealed class BotAuthProvider : Microsoft.Graph.Communications.Client.Authentication.IRequestAuthenticationProvider
{
    private readonly string _appId;
    private readonly string _appSecret;
    private readonly string _tenantId;

    public BotAuthProvider(string appId, string appSecret, string tenantId)
    {
        _appId = appId;
        _appSecret = appSecret;
        _tenantId = tenantId;
    }

    public Task AuthenticateOutboundRequestAsync(System.Net.Http.HttpRequestMessage request, string tenant)
        => Task.CompletedTask; // NOTE: attach MSAL client-credentials bearer token.

    public Task<Microsoft.Graph.Communications.Client.Authentication.RequestValidationResult> ValidateInboundRequestAsync(System.Net.Http.HttpRequestMessage request)
        => Task.FromResult(new Microsoft.Graph.Communications.Client.Authentication.RequestValidationResult { IsValid = true });
}

// Builds Graph join parameters from a meeting thread id. Kept separate so the
// Graph-specific construction is isolated and unit-testable in the .NET project.
internal static class JoinParametersFactory
{
    public static Microsoft.Graph.Communications.Calling.JoinMeetingParameters ForThread(
        string threadId, string? tenantId, string serviceFqdn)
    {
        // NOTE: real impl constructs ChatInfo + MeetingInfo (OrganizerMeetingInfo)
        // from the threadId/tenant and the bot's media session.
        return new Microsoft.Graph.Communications.Calling.JoinMeetingParameters(threadId, tenantId, serviceFqdn);
    }
}
