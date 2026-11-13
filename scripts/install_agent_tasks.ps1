$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$root = Split-Path -Parent $PSScriptRoot

$tasks = @(
    @{ Name = 'Mukana Scraper Agent'; Bat = Join-Path $desktop 'Start Mukana Scraper Agent.bat' },
    @{ Name = 'Mukana Apply Agent'; Bat = Join-Path $desktop 'Start Mukana Apply Agent.bat' },
    @{ Name = 'Mukana Matcher'; Bat = Join-Path $desktop 'Start Mukana Matcher.bat' },
    @{ Name = 'Mukana WhatsApp Gateway'; Bat = Join-Path $desktop 'Start Mukana WhatsApp Gateway.bat' }
)

foreach ($task in $tasks) {
    if (-not (Test-Path -LiteralPath $task.Bat)) {
        throw "Missing launcher: $($task.Bat)"
    }
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$($task.Bat)`"" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $task.Name -Action $action -Trigger $trigger -Settings $settings -Description 'Mukana local agent' -Force | Out-Null
    Write-Output "Registered $($task.Name)"
}

$python = 'C:\Users\mmash\.conda\envs\prefect_env\python.exe'
$backupAction = New-ScheduledTaskAction -Execute $python -Argument 'scripts\backup_neon.py' -WorkingDirectory $root
$backupTrigger = New-ScheduledTaskTrigger -Daily -At '02:00'
$backupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName 'Mukana Neon Backup' -Action $backupAction -Trigger $backupTrigger -Settings $backupSettings -Description 'Nightly Neon logical backup' -Force | Out-Null
Write-Output 'Registered Mukana Neon Backup'
