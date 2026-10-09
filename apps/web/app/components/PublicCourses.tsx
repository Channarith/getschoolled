import Link from "next/link";

/** Free samples for visitors who are not signed in. Full courses live on Live Class and Group Class. */
export function PublicCourses() {
  return (
    <section aria-label="Demo" style={{ width: "100%", maxWidth: 720, margin: "28px auto 0", textAlign: "left" }}>
      <h2 style={{ fontSize: 22, margin: "0 0 8px" }}>Demo</h2>
      <p style={{ margin: "0 0 12px" }}>
        Driver&apos;s Education is free for 10 minutes. Anyone can start it, with or without an account.
      </p>
      <p style={{ margin: "0 0 12px" }}>
        <Link href="/demo/drivers-ed"><button type="button">Start the free driver&apos;s ed demo</button></Link>
      </p>
      <p style={{ margin: "0 0 12px" }}>
        On the Go plays those same classes with audio only. No camera. It also stops at 10 minutes.
      </p>
      <p style={{ margin: "0 0 12px" }}>
        <Link href="/demo/on-the-go"><button type="button">Start the free audio demo</button></Link>
      </p>
      <p style={{ margin: "0 0 12px" }}>
        The vision arcade is free too. Children play machine-vision games from the webcam lab. The camera stays in the browser.
      </p>
      <p style={{ margin: "0 0 18px" }}>
        <Link href="/arcade#vision"><button type="button">Play the vision arcade</button></Link>
      </p>
    </section>
  );
}
