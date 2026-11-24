param(
    [string]$DeviceName = "HP True Vision FHD Camera",
    [string]$PublishUrl = "rtsp://127.0.0.1:8555/camera",
    [string]$Resolution = "1280x720",
    [int]$CaptureFps = 30,
    [int]$OutputFps = 15,
    [string]$FfmpegPath = "",
    [switch]$VerboseStream
)

$ErrorActionPreference = "Stop"

$ffmpegCandidates = @(
    $FfmpegPath,
    (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    (Join-Path $env:LOCALAPPDATA "Programs\codex-ffmpeg\9.0.2-essentials\bin\ffmpeg.exe")
)
$ffmpeg = $ffmpegCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1

if (-not $ffmpeg) {
    throw "ffmpeg.exe was not found. Install FFmpeg or pass -FfmpegPath."
}

Write-Host "Camera: $DeviceName"
Write-Host "Capture: $Resolution at ${CaptureFps}fps"
Write-Host "Stream: ${OutputFps}fps"
Write-Host "Publish URL: $PublishUrl"
Write-Host "Waiting for the Docker app. Press Ctrl+C to stop."

$logLevel = if ($VerboseStream) { "warning" } else { "quiet" }
$ffmpegArgs = @(
    "-hide_banner",
    "-loglevel", $logLevel,
    "-f", "dshow",
    "-rtbufsize", "32M",
    "-framerate", "$CaptureFps",
    "-video_size", $Resolution,
    "-i", "video=$DeviceName",
    "-an",
    "-vf", "fps=$OutputFps",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-pix_fmt", "yuv420p",
    "-g", "$OutputFps",
    "-f", "rtsp",
    "-rtsp_transport", "tcp",
    $PublishUrl
)

while ($true) {
    & $ffmpeg @ffmpegArgs
    Write-Host "Camera stream disconnected. Reconnecting..."
    Start-Sleep -Seconds 1
}
