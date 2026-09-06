param(
    [string]$Background = "$PSScriptRoot\..\assets\startup\fan-translation-background.png",
    [string]$QrCode = "$PSScriptRoot\..\assets\startup\telegram-qr.jpg",
    [string]$Output = "$PSScriptRoot\..\assets\startup\fan-translation-card.png"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$width = 1024
$height = 576
$canvas = New-Object System.Drawing.Bitmap($width, $height, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

$backgroundImage = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $Background))
$qrImage = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $QrCode))

try {
    $graphics.DrawImage($backgroundImage, 0, 0, $width, $height)
    $graphics.FillRectangle((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(115, 0, 4, 18))), 0, 0, $width, $height)

    $cyan = [System.Drawing.Color]::FromArgb(255, 71, 211, 255)
    $white = [System.Drawing.Color]::FromArgb(255, 242, 246, 255)
    $muted = [System.Drawing.Color]::FromArgb(255, 180, 195, 218)
    $panelBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(185, 2, 10, 32))
    $linePen = New-Object System.Drawing.Pen($cyan, 2)
    $graphics.FillRectangle($panelBrush, 60, 68, 626, 440)
    $graphics.DrawLine($linePen, 60, 68, 686, 68)
    $graphics.DrawLine($linePen, 60, 508, 686, 508)

    $titleFont = New-Object System.Drawing.Font('Segoe UI Semibold', 31, [System.Drawing.FontStyle]::Bold)
    $subtitleFont = New-Object System.Drawing.Font('Segoe UI', 18, [System.Drawing.FontStyle]::Regular)
    $bodyFont = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Regular)
    $smallFont = New-Object System.Drawing.Font('Segoe UI', 11, [System.Drawing.FontStyle]::Regular)
    $whiteBrush = New-Object System.Drawing.SolidBrush($white)
    $cyanBrush = New-Object System.Drawing.SolidBrush($cyan)
    $mutedBrush = New-Object System.Drawing.SolidBrush($muted)

    $graphics.DrawString('DRAMAtical Murder', $titleFont, $whiteBrush, 94, 103)
    $graphics.DrawString('РУССКИЙ ФАНАТСКИЙ ПЕРЕВОД', $subtitleFont, $cyanBrush, 97, 157)
    $graphics.DrawString("Спасибо, что установили русификатор!`n`nЭтот перевод создан энтузиастами для игроков`nи не связан с разработчиками или издателем игры.`n`nНашли ошибку, хотите оставить отзыв`nили предложить исправление? Присоединяйтесь`nк нашему Telegram-каналу.", $bodyFont, $whiteBrush, (New-Object System.Drawing.RectangleF(97, 215, 550, 230)))
    $graphics.DrawString('Приятной игры!', $subtitleFont, $cyanBrush, 97, 454)

    $qrBack = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $graphics.FillRectangle($qrBack, 748, 128, 220, 220)
    $graphics.DrawImage($qrImage, 758, 138, 200, 200)
    $qrFormat = New-Object System.Drawing.StringFormat
    $qrFormat.Alignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString('ОТЗЫВЫ И ПРЕДЛОЖЕНИЯ', $smallFont, $whiteBrush, (New-Object System.Drawing.RectangleF(724, 370, 268, 25)), $qrFormat)
    $graphics.DrawString('t.me/+OMNL2112F-pjMGIy', $smallFont, $mutedBrush, (New-Object System.Drawing.RectangleF(724, 399, 268, 25)), $qrFormat)
    $graphics.DrawString('Нажмите, чтобы продолжить', $smallFont, $mutedBrush, (New-Object System.Drawing.RectangleF(724, 475, 268, 25)), $qrFormat)

    $outputPath = [System.IO.Path]::GetFullPath($Output)
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($outputPath)) | Out-Null
    $canvas.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "Created $outputPath"
}
finally {
    $graphics.Dispose()
    $canvas.Dispose()
    $backgroundImage.Dispose()
    $qrImage.Dispose()
}
