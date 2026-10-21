import React from "react";
import { render } from "@testing-library/react-native";

import ScanRing from "../components/ScanRing";

jest.useFakeTimers();

describe("ScanRing", () => {
  it("renders at the guide size for every progress step without throwing", () => {
    for (const progress of [0, 0.2, 0.6, 1, 1.4, -1]) {
      const view = render(<ScanRing size={300} progress={progress} found={progress > 0.5} />);
      expect(view.getByTestId("scan-ring").props.style).toEqual(
        expect.arrayContaining([expect.objectContaining({ width: 300, height: 300 })]),
      );
      view.unmount();
    }
  });
});
