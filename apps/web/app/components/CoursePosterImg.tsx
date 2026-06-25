"use client";

import { useEffect, useState } from "react";
import { coursePosterUrl, defaultCoursePosterUrl, type CoursePosterInput } from "../lib/courseArtwork";

export function CoursePosterImg({
  input,
  className,
}: {
  input: CoursePosterInput;
  className?: string;
}) {
  const resolved = coursePosterUrl(input);
  const [src, setSrc] = useState(resolved);

  useEffect(() => {
    setSrc(resolved);
  }, [resolved]);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      className={className}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setSrc(defaultCoursePosterUrl())}
    />
  );
}
