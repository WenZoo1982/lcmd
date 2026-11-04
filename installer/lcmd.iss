
#define AppName "LCMD"
#define AppVersion "0.1.0-beta.1"
#define AppPublisher "WenZoo"
#define AppId "{{f0207588-13d8-4933-ba06-2ad0da918947}"

#ifndef SourceDir
  #define SourceDir "..\..\lcmd-releases\lcmd-0.1.0-beta.1-build"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\LCMD
DefaultGroupName=LCMD
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
UsePreviousAppDir=yes
OutputDir=..\..\lcmd-releases
OutputBaseFilename=LCMD-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes
SetupLogging=yes

[Files]
Source: "{#SourceDir}\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\knowledge\*"; DestDir: "{code:GetKnowledgeDir}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\knowledge-integrity.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\LCMD"; Filename: "{app}\lcmd.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\lcmd.exe"; Description: "启动 LCMD"; Flags: postinstall nowait skipifsilent

[Code]
const
  KnowledgeSettingsKey = 'Software\WenZoo\LCMD';

var
  KnowledgeDirPage: TInputDirWizardPage;

function GetKnowledgeDir(Param: String): String;
begin
  Result := KnowledgeDirPage.Values[0];
end;

function NormalizePath(const Value: String): String;
begin
  Result := RemoveBackslashUnlessRoot(
    ExpandFileName(RemoveQuotes(Trim(Value)))
  );
end;

function TryParseTomlString(
  const Value: String;
  var ParsedValue: String
): Boolean;
var
  I: Integer;
  Ch: Char;
  EscapeChar: Char;
  Closed: Boolean;
  Tail: String;
begin
  Result := False;
  ParsedValue := '';
  Closed := False;

  if (Length(Value) < 2) or (Value[1] <> '"') then
    Exit;

  I := 2;

  while I <= Length(Value) do
  begin
    Ch := Value[I];

    if Ch = '"' then
    begin
      Closed := True;
      Inc(I);
      Break;
    end;

    if Ch = '\' then
    begin
      Inc(I);

      if I > Length(Value) then
        Exit;

      EscapeChar := Value[I];

      if EscapeChar = '\' then
        ParsedValue := ParsedValue + '\'
      else if EscapeChar = '"' then
        ParsedValue := ParsedValue + '"'
      else
        Exit;
    end
    else
      ParsedValue := ParsedValue + Ch;

    Inc(I);
  end;

  if not Closed then
    Exit;

  Tail := Trim(Copy(Value, I, Length(Value) - I + 1));

  if (Tail <> '') and (Tail[1] <> '#') then
    Exit;

  if Trim(ParsedValue) = '' then
    Exit;

  Result := True;
end;

function TryGetConfigKnowledgeDir(
  var KnowledgeDir: String
): Boolean;
var
  ConfigFile: String;
  Lines: TArrayOfString;
  I: Integer;
  Line: String;
  Key: String;
  RawValue: String;
  ParsedValue: String;
  ParsedPath: String;
  PlatformValue: String;
  LanguageValue: String;
  EqualsPosition: Integer;
  SectionCount: Integer;
  PathCount: Integer;
  PlatformCount: Integer;
  LanguageCount: Integer;
  InKnowledgeSection: Boolean;
begin
  Result := False;
  KnowledgeDir := '';
  ParsedPath := '';
  PlatformValue := '';
  LanguageValue := '';

  SectionCount := 0;
  PathCount := 0;
  PlatformCount := 0;
  LanguageCount := 0;
  InKnowledgeSection := False;

  ConfigFile :=
    ExpandConstant('{localappdata}\lcmd\config.toml');

  if not LoadStringsFromFile(ConfigFile, Lines) then
    Exit;

  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);

    if Line = '' then
      Continue;

    if Line[1] = '#' then
      Continue;

    if Line[1] = '[' then
    begin
      Inc(SectionCount);

      if (SectionCount <> 1) or
         (CompareText(Line, '[knowledge]') <> 0) then
        Exit;

      InKnowledgeSection := True;
      Continue;
    end;

    if not InKnowledgeSection then
      Exit;

    EqualsPosition := Pos('=', Line);

    if EqualsPosition = 0 then
      Exit;

    Key := Trim(Copy(Line, 1, EqualsPosition - 1));

    RawValue := Trim(
      Copy(
        Line,
        EqualsPosition + 1,
        Length(Line) - EqualsPosition
      )
    );

    if not TryParseTomlString(RawValue, ParsedValue) then
      Exit;

    if CompareText(Key, 'path') = 0 then
    begin
      Inc(PathCount);

      if PathCount <> 1 then
        Exit;

      ParsedPath := ParsedValue;
    end
    else if CompareText(Key, 'platform') = 0 then
    begin
      Inc(PlatformCount);

      if PlatformCount <> 1 then
        Exit;

      PlatformValue := ParsedValue;
    end
    else if CompareText(Key, 'language') = 0 then
    begin
      Inc(LanguageCount);

      if LanguageCount <> 1 then
        Exit;

      LanguageValue := ParsedValue;
    end
    else
      Exit;
  end;

  if (SectionCount <> 1) or
     (PathCount <> 1) or
     (PlatformCount <> 1) or
     (LanguageCount <> 1) then
    Exit;

  if not PathIsRooted(ParsedPath) then
    Exit;

  if not DirExists(ParsedPath) then
    Exit;

  KnowledgeDir := NormalizePath(ParsedPath);
  Result := True;
end;

function TryGetSavedKnowledgeDir(
  var KnowledgeDir: String
): Boolean;
var
  SavedKnowledgeDir: String;
begin
  Result := False;
  KnowledgeDir := '';

  if not RegQueryStringValue(
    HKEY_CURRENT_USER,
    KnowledgeSettingsKey,
    'KnowledgeDir',
    SavedKnowledgeDir
  ) then
    Exit;

  SavedKnowledgeDir := Trim(SavedKnowledgeDir);

  if SavedKnowledgeDir = '' then
    Exit;

  if not PathIsRooted(SavedKnowledgeDir) then
    Exit;

  if not DirExists(SavedKnowledgeDir) then
    Exit;

  KnowledgeDir := NormalizePath(SavedKnowledgeDir);
  Result := True;
end;

function GetInitialKnowledgeDir: String;
var
  KnowledgeDir: String;
begin
  if TryGetConfigKnowledgeDir(KnowledgeDir) then
  begin
    Result := KnowledgeDir;
    Exit;
  end;

  if TryGetSavedKnowledgeDir(KnowledgeDir) then
  begin
    Result := KnowledgeDir;
    Exit;
  end;

  Result := ExpandConstant('{localappdata}\lcmd\knowledge');
end;

procedure InitializeWizard;
begin
  KnowledgeDirPage :=
    CreateInputDirPage(
      wpSelectDir,
      '知识库安装位置',
      '选择 LCMD 知识库的安装目录',
      '请选择知识库根目录。安装后，LCMD 将从此目录读取命令文档。',
      False,
      ''
    );

  KnowledgeDirPage.Add('知识库根目录：');
  KnowledgeDirPage.Values[0] := GetInitialKnowledgeDir;
end;

function IsSamePath(
  const LeftPath,
  RightPath: String
): Boolean;
begin
  Result := CompareText(
    NormalizePath(LeftPath),
    NormalizePath(RightPath)
  ) = 0;
end;

function UserPathContains(
  const PathValue,
  TargetPath: String
): Boolean;
var
  Remaining: String;
  Item: String;
  SeparatorPosition: Integer;
begin
  Result := False;
  Remaining := PathValue;

  while True do
  begin
    SeparatorPosition := Pos(';', Remaining);

    if SeparatorPosition > 0 then
    begin
      Item := Copy(Remaining, 1, SeparatorPosition - 1);
      Delete(Remaining, 1, SeparatorPosition);
    end
    else
    begin
      Item := Remaining;
      Remaining := '';
    end;

    if (Trim(Item) <> '') and IsSamePath(Item, TargetPath) then
    begin
      Result := True;
      Exit;
    end;

    if SeparatorPosition = 0 then
      Break;
  end;
end;

procedure AddToUserPath;
var
  ExistingPath: String;
  NewPath: String;
  AppPath: String;
begin
  AppPath := ExpandConstant('{app}');

  if not RegQueryStringValue(
    HKEY_CURRENT_USER,
    'Environment',
    'Path',
    ExistingPath
  ) then
    ExistingPath := '';

  if UserPathContains(ExistingPath, AppPath) then
    Exit;

  if ExistingPath = '' then
    NewPath := AppPath
  else
    NewPath := ExistingPath + ';' + AppPath;

  if not RegWriteExpandStringValue(
    HKEY_CURRENT_USER,
    'Environment',
    'Path',
    NewPath
  ) then
    RaiseException('无法写入当前用户 PATH 环境变量。');
end;

procedure RemoveFromUserPath;
var
  ExistingPath: String;
  NewPath: String;
  Remaining: String;
  Item: String;
  SeparatorPosition: Integer;
  FirstItem: Boolean;
  AppPath: String;
begin
  AppPath := ExpandConstant('{app}');

  if not RegQueryStringValue(
    HKEY_CURRENT_USER,
    'Environment',
    'Path',
    ExistingPath
  ) then
    Exit;

  NewPath := '';
  Remaining := ExistingPath;
  FirstItem := True;

  while True do
  begin
    SeparatorPosition := Pos(';', Remaining);

    if SeparatorPosition > 0 then
    begin
      Item := Copy(Remaining, 1, SeparatorPosition - 1);
      Delete(Remaining, 1, SeparatorPosition);
    end
    else
    begin
      Item := Remaining;
      Remaining := '';
    end;

    if (Trim(Item) = '') or not IsSamePath(Item, AppPath) then
    begin
      if not FirstItem then
        NewPath := NewPath + ';';

      NewPath := NewPath + Item;
      FirstItem := False;
    end;

    if SeparatorPosition = 0 then
      Break;
  end;

  if NewPath <> ExistingPath then
  begin
    if not RegWriteExpandStringValue(
      HKEY_CURRENT_USER,
      'Environment',
      'Path',
      NewPath
    ) then
      MsgBox(
        '无法从当前用户 PATH 中移除 LCMD 路径，请手动检查环境变量。',
        mbError,
        MB_OK
      );
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  KnowledgePath: String;
begin
  Result := True;

  if CurPageID = KnowledgeDirPage.ID then
  begin
    KnowledgePath := Trim(KnowledgeDirPage.Values[0]);

    if (KnowledgePath = '') or not PathIsRooted(KnowledgePath) then
    begin
      MsgBox(
        '请输入有效的绝对路径作为知识库安装目录。',
        mbError,
        MB_OK
      );
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not RegWriteStringValue(
      HKEY_CURRENT_USER,
      KnowledgeSettingsKey,
      'KnowledgeDir',
      NormalizePath(KnowledgeDirPage.Values[0])
    ) then
      RaiseException('无法保存 LCMD 知识库安装目录。');

    AddToUserPath;
  end;
end;

procedure CurUninstallStepChanged(
  CurUninstallStep: TUninstallStep
);
begin
  if CurUninstallStep = usUninstall then
    RemoveFromUserPath;
end;
