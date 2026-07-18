using System.Collections.Generic;
using UnityEngine;

namespace Salareen.Xr
{
    /// <summary>
    /// Quest lab session glue: buffers controller/hand actions and submits via XrProtocolClient.
    /// Attach to a scene root; set BaseUrl / RoomId / ParticipantId from deep-link or login handoff.
    /// </summary>
    public class XrLabSession : MonoBehaviour
    {
        public XrProtocolClient Client = new XrProtocolClient();
        public bool AutoEnableOnStart = false;

        readonly List<XrProtocolClient.Observation> _buffer = new List<XrProtocolClient.Observation>();
        int _seq = 1;

        async void Start()
        {
            if (AutoEnableOnStart && !string.IsNullOrEmpty(Client.RoomId))
            {
                try { await Client.EnableLabAsync(); }
                catch (System.Exception ex) { Debug.LogWarning("[Salareen XR] enable: " + ex.Message); }
            }
        }

        public void RecordAction(string action, string targetId, string hand = "right", float confidence = 0.9f, int holdMs = 0)
        {
            _buffer.Add(new XrProtocolClient.Observation
            {
                seq = _seq++,
                action = (action ?? "").Trim().ToLowerInvariant(),
                target_id = targetId ?? "",
                hand = hand ?? "",
                confidence = confidence,
                hold_ms = holdMs,
                ts_ms = System.DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            });
        }

        public async void SubmitBuffered()
        {
            try
            {
                var json = await Client.CompleteAsync(new List<XrProtocolClient.Observation>(_buffer));
                Debug.Log("[Salareen XR] result: " + json);
                _buffer.Clear();
            }
            catch (System.Exception ex)
            {
                Debug.LogError("[Salareen XR] complete failed: " + ex.Message);
            }
        }

        public async void SubmitDemoPass()
        {
            try
            {
                var json = await Client.CompleteAsync(XrProtocolClient.DemoPassObservations());
                Debug.Log("[Salareen XR] demo pass: " + json);
            }
            catch (System.Exception ex)
            {
                Debug.LogError("[Salareen XR] demo failed: " + ex.Message);
            }
        }
    }
}
