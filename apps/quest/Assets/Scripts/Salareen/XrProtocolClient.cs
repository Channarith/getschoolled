using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace Salareen.Xr
{
    /// <summary>
    /// Shared aoep.xr.v1 HTTP client for Quest Unity OpenXR builds.
    /// Mirrors apps/web/app/lib/xr.ts observation shapes.
    /// </summary>
    public class XrProtocolClient
    {
        public string BaseUrl = "https://api.salareen.com/orchestrator";
        public string RoomId = "";
        public string ParticipantId = "";
        public string StudentId = "";
        public string ModeratorKey = "";
        public string AuthBearer = "";

        [Serializable]
        public class Observation
        {
            public int seq;
            public string action;
            public string target_id;
            public string hand;
            public float confidence = 1f;
            public int hold_ms;
            public long ts_ms;
        }

        public async Task<string> GetLabJsonAsync()
        {
            var url = $"{BaseUrl.TrimEnd('/')}/api/live-rooms/{Uri.EscapeDataString(RoomId)}/xr/lab";
            using var req = UnityWebRequest.Get(url);
            AttachAuth(req);
            var op = req.SendWebRequest();
            while (!op.isDone) await Task.Yield();
            EnsureOk(req);
            return req.downloadHandler.text;
        }

        public async Task<string> EnableLabAsync(string title = "Demonstrate the learned action")
        {
            var url = $"{BaseUrl.TrimEnd('/')}/api/live-rooms/{Uri.EscapeDataString(RoomId)}/xr/enable";
            var body =
                "{\"moderator_key\":\"" + Escape(ModeratorKey) +
                "\",\"participant_id\":\"" + Escape(ParticipantId) +
                "\",\"enabled\":true,\"title\":\"" + Escape(title) + "\"}";
            using var req = new UnityWebRequest(url, "POST");
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            AttachAuth(req);
            var op = req.SendWebRequest();
            while (!op.isDone) await Task.Yield();
            EnsureOk(req);
            return req.downloadHandler.text;
        }

        public async Task<string> CompleteAsync(List<Observation> observations)
        {
            var url = $"{BaseUrl.TrimEnd('/')}/api/live-rooms/{Uri.EscapeDataString(RoomId)}/xr/complete";
            var body = BuildCompleteJson(observations);
            using var req = new UnityWebRequest(url, "POST");
            req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(body));
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            AttachAuth(req);
            var op = req.SendWebRequest();
            while (!op.isDone) await Task.Yield();
            EnsureOk(req);
            return req.downloadHandler.text;
        }

        public static List<Observation> DemoPassObservations()
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return new List<Observation>
            {
                new Observation { seq = 1, action = "approach", target_id = "station", confidence = 0.95f, ts_ms = now },
                new Observation { seq = 2, action = "grab", target_id = "tool", confidence = 0.9f, hold_ms = 600, ts_ms = now + 500 },
                new Observation { seq = 3, action = "confirm", target_id = "finish", confidence = 0.92f, hold_ms = 200, ts_ms = now + 1200 },
            };
        }

        public static List<Observation> DemoNeedsWorkObservations()
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            return new List<Observation>
            {
                new Observation { seq = 1, action = "approach", target_id = "station", confidence = 0.8f, ts_ms = now },
            };
        }

        string BuildCompleteJson(List<Observation> observations)
        {
            var sb = new StringBuilder();
            sb.Append("{\"participant_id\":\"").Append(Escape(ParticipantId)).Append("\",");
            sb.Append("\"student_id\":\"").Append(Escape(StudentId)).Append("\",");
            sb.Append("\"client_kind\":\"unity_openxr\",\"observations\":[");
            if (observations != null)
            {
                for (var i = 0; i < observations.Count; i++)
                {
                    var o = observations[i];
                    if (i > 0) sb.Append(',');
                    sb.Append('{');
                    sb.Append("\"seq\":").Append(o.seq).Append(',');
                    sb.Append("\"action\":\"").Append(Escape(o.action)).Append("\",");
                    sb.Append("\"target_id\":\"").Append(Escape(o.target_id)).Append("\",");
                    sb.Append("\"hand\":\"").Append(Escape(o.hand)).Append("\",");
                    sb.Append("\"confidence\":").Append(o.confidence.ToString(System.Globalization.CultureInfo.InvariantCulture)).Append(',');
                    sb.Append("\"hold_ms\":").Append(o.hold_ms).Append(',');
                    sb.Append("\"ts_ms\":").Append(o.ts_ms);
                    sb.Append('}');
                }
            }
            sb.Append("]}");
            return sb.ToString();
        }

        void AttachAuth(UnityWebRequest req)
        {
            if (!string.IsNullOrEmpty(AuthBearer))
                req.SetRequestHeader("Authorization", "Bearer " + AuthBearer);
        }

        static void EnsureOk(UnityWebRequest req)
        {
#if UNITY_2020_2_OR_NEWER
            if (req.result != UnityWebRequest.Result.Success)
#else
            if (req.isNetworkError || req.isHttpError)
#endif
                throw new Exception(req.error + " " + (req.downloadHandler != null ? req.downloadHandler.text : ""));
        }

        static string Escape(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
