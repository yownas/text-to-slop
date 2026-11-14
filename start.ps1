# text-to-slop script for poor Windows users

function Get-MenuSelection {
    param(
        [String[]]$MenuItems = @("Exit"),
        [String]$MenuPrompt = "Select an option"
    )
    $cursorPosition = $host.UI.RawUI.CursorPosition
    $pos = 0
    $key = $null

    function Write-Menu {
        param ([int]$selectedItemIndex)
        $Host.UI.RawUI.CursorPosition = $cursorPosition
        Write-Host $MenuPrompt -ForegroundColor Green
        for ($i = 0; $i -lt $MenuItems.Count; $i++) {
            $line = "    $($i+1) $($MenuItems[$i])"
            if ($selectedItemIndex -eq $i) {
                Write-Host $line -ForegroundColor Blue -BackgroundColor Gray
            } else {
                Write-Host $line
            }
        }
    }

    Write-Menu -selectedItemIndex $pos
    while ($key -ne 13) {
        $press = $host.ui.rawui.readkey("NoEcho,IncludeKeyDown")
        $key = $press.virtualkeycode
        if ($key -eq 38) { $pos-- }
        if ($key -eq 40) { $pos++ }
        if ($pos -lt 0) { $pos = 0 }
        if ($pos -eq $MenuItems.Count) { $pos = $MenuItems.Count - 1 }
        Write-Menu -selectedItemIndex $pos
    }
    return "$($pos+1)"
}

# Status bar
function Status-Bar {
    $got_python = Test-Path -Path "bin"
    $got_tts = Test-Path -Path "tts"
    $chars = [ordered]@{'True'='Installed';'False'='Not found'}
    Write-Host "Python: $($chars["$got_python"]) | Text-To-Slop: $($chars["$got_tts"])"
}

# Loop Python
function Install-Python {
    param(
        [String]$Version = "3.13.13"
    )
    Write-Host "Please wait, downloading python $Version and some required modules."

    $Url = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"
    $Result = "bin"
    $Dl = "data/dl"

    if (Test-Path $Result) {
        Write-Host "$Result already exists. To change python version you need to manually remove or rename the old $Result folder."
        return
    }

    if (-not (Test-Path $Dl)) {
        New-Item -ItemType Directory -Path $Dl | Out-Null
    }

    New-Item -ItemType Directory -Path $Result | Out-Null

    # Download embedded Python
    Invoke-WebRequest -Uri $Url -OutFile "$Dl\embed.zip"

    # Extract archive
    Expand-Archive -Path "$Dl\embed.zip" -DestinationPath $Result

    # Rename *_pth -> *.pth
    Get-ChildItem "$Result\python*._pth" | ForEach-Object {
        $NewName = $_.Name -replace '_pth$', 'pth'
        Rename-Item -Path $_.FullName -NewName $NewName
    }

    # Enable site-packages
    $PthFile = Get-ChildItem "$Result\python*.pth" | Select-Object -First 1
    Add-Content -Path $PthFile.FullName -Value "import site"

    # Download get-pip.py
    Invoke-WebRequest `
        -Uri "https://bootstrap.pypa.io/get-pip.py" `
        -OutFile "$Result\get-pip.py"

    # Install pip
    & "$Result\python.exe" "$Result\get-pip.py"

    # Install packages
    & "$Result\Scripts\pip.exe" install `
        wheel `
        packaging `
        pygit2 `
        setuptools==80.9.0 `
        cffi==2.0.0

    Write-Host "Done..."
}
function Loop-Python {
    do {
        Clear
        Status-Bar
        $input = Get-MenuSelection @("3.13.13", "Back") "Select python version"
        switch ($input) {
            '1' { Install-Python "3.13.13"; Pause }
            '2' { return }
        }
    } until ($input -eq "$MenuItems.Count")
}

# Install TTS
function Get-TTS {
    param(
        [String]$Branch = "main"
    )
    $Repo = "https://github.com/yownas/text-to-slop.git"
    if ($selectedItemIndex -eq $i) {
        Write-Host "Please wait. Cloning branch $Branch from $Repo"
        bin\python.exe -c "import pygit2;pygit2.clone_repository('$Repo', 'tts', checkout_branch='$Branch')"
    } else {
        Write-Host "Updating from $Repo"
	bin\python.exe -c "import pygit2;r=pygit2.Repository('tts');r.remotes['origin'].fetch();t=r.lookup_reference('refs/remotes/origin/$Branch').target;r.checkout_tree(r.get(t));r.head.set_target(t)"
    }
    Write-Host "Done..."
    Pause
}

# Start TTS
function Start-TTS {
    if (-not (Test-Path -Path "bin")) {
        Write-Host "Sorry, you need to install python first."
        Pause
        return
    }
    if (-not (Test-Path -Path "tts")) {
        Write-Host "Sorry, you need to get Text-To-Slop first."
        Pause
        return
    }
    Write-Host "Starting TTS..."
    .\bin\python.exe -s tts/launch.py
    pause
}

# Main loop
do {
    Clear
    Status-Bar
    $input = Get-MenuSelection @(
        "Select python",
        "Install or update Text-To-Slop",
        "Start webfui",
        "Exit"
    )
    switch ($input) {
        '1' { Loop-Python }
        '2' { Get-TTS }
        '3' { Start-TTS }
        '4' { return }
    }
} until ($input -eq "$MenuItems.Count")
