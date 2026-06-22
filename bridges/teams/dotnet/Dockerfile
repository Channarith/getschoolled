# Teams <-> LiveKit media bridge sidecar (phase 8).
# Build where a .NET 8 SDK is available; not built in the Cursor sandbox.
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY TeamsBridge.csproj ./
RUN dotnet restore TeamsBridge.csproj
COPY . ./
RUN dotnet publish TeamsBridge.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app ./
# Control plane the Python bridge talks to (TEAMS_BRIDGE_SIDECAR_URL).
EXPOSE 8080
# Media ports for the Graph media platform (TCP/UDP) are configured per deploy.
ENTRYPOINT ["dotnet", "aoep-teams-bridge.dll"]
