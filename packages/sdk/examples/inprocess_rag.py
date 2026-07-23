"""Embed AOEP's local retrieval capability without running a service."""

from aoep_sdk.inprocess import Document, RagIndex


def main() -> None:
    index = RagIndex(
        [
            Document.from_text(
                "python-loops",
                "Python loops",
                "A for loop repeats work for every item in an iterable.",
            ),
            Document.from_text(
                "python-functions",
                "Python functions",
                "A function groups reusable behavior and can return a value.",
            ),
        ]
    )

    for result in index.retrieve("How do I repeat work?", top_k=2):
        print(f"{result.document.title}: {result.score:.3f}")


if __name__ == "__main__":
    main()
