"use client";

import { CourseClassGate } from "../../components/CourseClassGate";

export default function DriversEdPage() {
  return (
    <CourseClassGate
      courseId="drivers-ed"
      title="Driver's Education"
      demoHref="/demo/drivers-ed"
    />
  );
}
