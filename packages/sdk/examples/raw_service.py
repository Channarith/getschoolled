"""Call a newer endpoint through the forward-compatible raw client."""

from aoep_sdk import AOEPClient, NotFoundError


def main() -> None:
    client = AOEPClient()
    training = client.service("orchestrator")

    try:
        capabilities = training.request("GET", "/api/training/capabilities")
    except NotFoundError as exc:
        print(f"The connected platform does not expose this capability: {exc}")
        return

    print(f"Canonical package: {capabilities['canonical_package']}")
    for name, suite in capabilities.get("suites", {}).items():
        print(f"{name}: {suite['description']}")


if __name__ == "__main__":
    main()
