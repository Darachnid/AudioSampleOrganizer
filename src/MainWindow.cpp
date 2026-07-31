#include "MainWindow.h"

#include "AudioEngine.h"
#include "ClipExporter.h"
#include "ClipModel.h"
#include "MetadataStore.h"
#include "StatusDialog.h"

#include <QAccessible>
#include <QDir>
#include <QEvent>
#include <QFileDialog>
#include <QFileInfo>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPushButton>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>

#include <cmath>

MainWindow::MainWindow(const QString &projectRoot, QWidget *parent)
    : QMainWindow(parent)
    , m_projectRoot(projectRoot)
{
    setWindowTitle(QStringLiteral("ClipMark"));
    resize(900, 640);
    setAccessibleName(QStringLiteral("ClipMark main window"));
    setAccessibleDescription(
        QStringLiteral("Accessible WAV clip marker. Press E for status, Shift+E for detail."));

    m_audio = new AudioEngine(this);
    m_clip = new ClipModel(m_audio, this);
    m_metadata = new MetadataStore(
        QDir(m_projectRoot).filePath(QStringLiteral("sample_metadata.json")),
        this);

    buildUi();

    m_statusDialog = new StatusDialog(this);

    m_tickTimer = new QTimer(this);
    m_tickTimer->setInterval(50);
    connect(m_tickTimer, &QTimer::timeout, this, &MainWindow::onTick);
    m_tickTimer->start();

    m_shuttleTimer = new QTimer(this);
    m_shuttleTimer->setInterval(100);
    connect(m_shuttleTimer, &QTimer::timeout, this, [this]() {
        if (m_shuttleDirection == 0) {
            return;
        }
        double speed = 1.0;
        const qint64 heldMs = m_shuttleHeld.elapsed();
        if (heldMs > 4000) {
            speed = 8.0;
        } else if (heldMs > 2000) {
            speed = 4.0;
        } else if (heldMs > 1000) {
            speed = 2.0;
        }
        m_audio->seekSeconds(
            m_audio->positionSeconds() + (0.1 * speed * m_shuttleDirection));
        refreshUi();
    });

    connect(m_audio, &AudioEngine::statusMessage, this, &MainWindow::setStatus);
    connect(m_clip, &ClipModel::statusMessageChanged, this, &MainWindow::setStatus);
    connect(m_clip, &ClipModel::changed, this, &MainWindow::refreshUi);
    connect(m_audio, &AudioEngine::positionChanged, this, [this](double) {
        refreshUi();
    });

    setStatus(QStringLiteral(
        "Open a WAV file to begin. Press E for status, Shift+E for detail."));
    refreshUi();
}

MainWindow::~MainWindow() = default;

void MainWindow::buildUi()
{
    auto *central = new QWidget(this);
    central->setFocusPolicy(Qt::StrongFocus);
    setCentralWidget(central);
    auto *layout = new QVBoxLayout(central);

    m_titleLabel = new QLabel(QStringLiteral("ClipMark"), central);
    QFont titleFont = m_titleLabel->font();
    titleFont.setPointSize(titleFont.pointSize() + 6);
    titleFont.setBold(true);
    m_titleLabel->setFont(titleFont);
    m_titleLabel->setAccessibleName(QStringLiteral("Application title"));
    layout->addWidget(m_titleLabel);

    m_openButton = new QPushButton(QStringLiteral("Open WAV…"), central);
    m_openButton->setAccessibleName(QStringLiteral("Open WAV file"));
    m_openButton->setShortcut(QKeySequence::Open);
    connect(m_openButton, &QPushButton::clicked, this, &MainWindow::openAudioFile);
    layout->addWidget(m_openButton);

    m_modeLabel = new QLabel(central);
    m_modeLabel->setAccessibleName(QStringLiteral("Current mode"));
    layout->addWidget(m_modeLabel);

    m_fileLabel = new QLabel(central);
    m_fileLabel->setAccessibleName(QStringLiteral("Source file"));
    m_fileLabel->setWordWrap(true);
    layout->addWidget(m_fileLabel);

    m_exportLabel = new QLabel(central);
    m_exportLabel->setAccessibleName(QStringLiteral("Export directory"));
    m_exportLabel->setWordWrap(true);
    layout->addWidget(m_exportLabel);

    m_transportLabel = new QLabel(central);
    m_transportLabel->setAccessibleName(QStringLiteral("Transport state"));
    layout->addWidget(m_transportLabel);

    m_positionLabel = new QLabel(central);
    m_positionLabel->setAccessibleName(QStringLiteral("Playback position"));
    layout->addWidget(m_positionLabel);

    m_volumeLabel = new QLabel(central);
    m_volumeLabel->setAccessibleName(QStringLiteral("Playback volume"));
    layout->addWidget(m_volumeLabel);

    m_startLabel = new QLabel(central);
    m_startLabel->setAccessibleName(QStringLiteral("Clip start"));
    layout->addWidget(m_startLabel);

    m_endLabel = new QLabel(central);
    m_endLabel->setAccessibleName(QStringLiteral("Clip end"));
    layout->addWidget(m_endLabel);

    m_lengthLabel = new QLabel(central);
    m_lengthLabel->setAccessibleName(QStringLiteral("Clip length"));
    layout->addWidget(m_lengthLabel);

    m_sourceEdit = new QLineEdit(central);
    m_sourceEdit->setPlaceholderText(QStringLiteral("Sound source"));
    m_sourceEdit->setAccessibleName(QStringLiteral("Sound source"));
    m_sourceEdit->setAccessibleDescription(
        QStringLiteral("Name of the sound source for the exported filename."));
    m_sourceEdit->installEventFilter(this);
    layout->addWidget(m_sourceEdit);

    m_nameEdit = new QLineEdit(central);
    m_nameEdit->setPlaceholderText(QStringLiteral("Sample name"));
    m_nameEdit->setAccessibleName(QStringLiteral("Sample name"));
    m_nameEdit->setAccessibleDescription(
        QStringLiteral("Sample name for the exported filename."));
    m_nameEdit->installEventFilter(this);
    layout->addWidget(m_nameEdit);

    m_controlsLabel = new QLabel(central);
    m_controlsLabel->setWordWrap(true);
    m_controlsLabel->setAccessibleName(QStringLiteral("Controls for current mode"));
    layout->addWidget(m_controlsLabel);

    m_messageLabel = new QLabel(central);
    m_messageLabel->setWordWrap(true);
    m_messageLabel->setAccessibleName(QStringLiteral("Status message"));
    m_messageLabel->setAccessibleDescription(
        QStringLiteral("Latest ClipMark status message."));
    layout->addWidget(m_messageLabel);

    layout->addStretch(1);

    // Live region style: message updates announce through accessible name changes.
    m_messageLabel->setTextInteractionFlags(Qt::TextSelectableByKeyboard);
}

void MainWindow::openAudioFile()
{
    const QString path = QFileDialog::getOpenFileName(
        this,
        QStringLiteral("Open WAV file"),
        m_projectRoot,
        QStringLiteral("WAV files (*.wav)"));

    if (path.isEmpty()) {
        return;
    }

    QString error;
    if (!m_audio->load(QUrl::fromLocalFile(path), &error)) {
        QMessageBox::warning(this, QStringLiteral("ClipMark"), error);
        return;
    }

    m_metadata->setAudioPath(path);
    delete m_exporter;
    m_exporter = new ClipExporter(
        path,
        QDir(m_projectRoot).filePath(QStringLiteral("ExportedSamples")),
        m_clip,
        m_metadata,
        this);

    m_clip->clearAfterExport();
    setMode(AppMode::Edit);
    setStatus(QStringLiteral("Loaded %1.").arg(m_audio->fileName()));
    refreshUi();

    QAccessibleAnnouncementEvent announcement(
        this,
        QStringLiteral("Loaded %1. Edit mode.").arg(m_audio->fileName()));
    QAccessible::updateAccessibility(&announcement);
}

bool MainWindow::ensureLoaded()
{
    if (m_audio->filePath().isEmpty()) {
        setStatus(QStringLiteral("Open a WAV file first."));
        return false;
    }
    return true;
}

void MainWindow::setMode(AppMode mode)
{
    m_mode = mode;
    updateModeWidgets();
    refreshUi();

    QAccessibleAnnouncementEvent announcement(
        this,
        QString::fromUtf8(appModeLabel(mode)));
    QAccessible::updateAccessibility(&announcement);
}

void MainWindow::setStatus(const QString &message)
{
    m_statusMessage = message;
    m_messageLabel->setText(QStringLiteral("Message: %1").arg(message));

    QAccessibleEvent event(m_messageLabel, QAccessible::NameChanged);
    QAccessible::updateAccessibility(&event);
}

void MainWindow::updateModeWidgets()
{
    const bool sourceMode = m_mode == AppMode::Source;
    const bool nameMode = m_mode == AppMode::Name;
    const bool naming = sourceMode || nameMode || m_mode == AppMode::Final;

    m_sourceEdit->setVisible(naming);
    m_nameEdit->setVisible(nameMode || m_mode == AppMode::Final);
    m_sourceEdit->setEnabled(sourceMode);
    m_nameEdit->setEnabled(nameMode);

    if (sourceMode) {
        m_sourceEdit->setFocus(Qt::OtherFocusReason);
    } else if (nameMode) {
        m_nameEdit->setFocus(Qt::OtherFocusReason);
    } else {
        centralWidget()->setFocus(Qt::OtherFocusReason);
    }
}

QString MainWindow::formatTime(double seconds) const
{
    seconds = qMax(0.0, seconds);
    const int hours = static_cast<int>(seconds) / 3600;
    const int minutes = (static_cast<int>(seconds) % 3600) / 60;
    const double remain = std::fmod(seconds, 60.0);
    if (hours > 0) {
        return QStringLiteral("%1:%2:%3")
            .arg(hours, 2, 10, QLatin1Char('0'))
            .arg(minutes, 2, 10, QLatin1Char('0'))
            .arg(remain, 4, 'f', 1, QLatin1Char('0'));
    }
    return QStringLiteral("%1:%2")
        .arg(minutes, 2, 10, QLatin1Char('0'))
        .arg(remain, 4, 'f', 1, QLatin1Char('0'));
}

void MainWindow::refreshUi()
{
    m_modeLabel->setText(
        QStringLiteral("Mode: %1").arg(QString::fromUtf8(appModeLabel(m_mode))));

    m_fileLabel->setText(
        m_audio->filePath().isEmpty()
            ? QStringLiteral("File: (none)")
            : QStringLiteral("File: %1").arg(m_audio->fileName()));

    const QString exportDir = m_exporter
        ? m_exporter->exportDirectory()
        : QDir(m_projectRoot).filePath(QStringLiteral("ExportedSamples"));
    m_exportLabel->setText(QStringLiteral("Export to: %1").arg(exportDir));

    QString transport = m_audio->isPlaying()
        ? QStringLiteral("Playing")
        : QStringLiteral("Paused");
    if (m_mode == AppMode::Preview) {
        transport = m_audio->isPlaying()
            ? QStringLiteral("Previewing sample")
            : QStringLiteral("Preview paused");
    } else if (m_shuttleDirection != 0) {
        transport = m_shuttleDirection < 0
            ? QStringLiteral("Seeking reverse")
            : QStringLiteral("Seeking forward");
    }
    m_transportLabel->setText(QStringLiteral("Transport: %1").arg(transport));

    m_positionLabel->setText(
        QStringLiteral("Position: %1 / %2")
            .arg(formatTime(m_audio->positionSeconds()),
                 formatTime(m_audio->durationSeconds())));
    m_volumeLabel->setText(
        QStringLiteral("Volume: %1%").arg(m_audio->volumePercent()));

    m_startLabel->setText(
        QStringLiteral("Start: %1")
            .arg(m_clip->startSeconds()
                     ? formatTime(*m_clip->startSeconds())
                     : QStringLiteral("Not selected")));
    m_endLabel->setText(
        QStringLiteral("End: %1")
            .arg(m_clip->endSeconds()
                     ? formatTime(*m_clip->endSeconds())
                     : QStringLiteral("Not selected")));

    if (m_clip->isValid()) {
        m_lengthLabel->setText(
            QStringLiteral("Length: %1")
                .arg(formatTime(*m_clip->endSeconds() - *m_clip->startSeconds())));
    } else {
        m_lengthLabel->setText(QStringLiteral("Length: —"));
    }

    if (m_mode == AppMode::Edit) {
        m_controlsLabel->setText(
            QStringLiteral(
                "Controls: Space play/pause. Left/Right seek. Up/Down volume. "
                "A start. D end. Enter preview. E status. Shift+E detail. Q quit."));
    } else if (m_mode == AppMode::Preview) {
        m_controlsLabel->setText(
            QStringLiteral(
                "Controls: Enter continue. Right replay. Other key adjust. "
                "E status. Shift+E detail. Q quit."));
    } else if (m_mode == AppMode::Source) {
        m_controlsLabel->setText(
            QStringLiteral(
                "Controls: Type source name. Enter continue. Left back. "
                "F1 status. F2 detail. Q quit."));
    } else if (m_mode == AppMode::Name) {
        m_controlsLabel->setText(
            QStringLiteral(
                "Controls: Type sample name. Enter continue. Left back. "
                "F1 status. F2 detail. Q quit."));
    } else {
        m_controlsLabel->setText(
            QStringLiteral(
                "Controls: Enter export. Left back. Down cancel. "
                "E status. Shift+E detail. Q quit."));
    }

    m_messageLabel->setText(QStringLiteral("Message: %1").arg(m_statusMessage));
}

void MainWindow::onTick()
{
    if (m_mode == AppMode::Preview) {
        m_clip->updatePreview();
    }
}

int MainWindow::volumeStep(int currentPercent) const
{
    if (currentPercent <= 5) {
        return 1;
    }
    if (currentPercent <= 10) {
        return 2;
    }
    if (currentPercent <= 25) {
        return 5;
    }
    return 10;
}

void MainWindow::changeVolume(int direction)
{
    const int current = m_audio->volumePercent();
    const int step = volumeStep(current);
    m_audio->setVolumePercent(current + direction * step);
    refreshUi();
}

void MainWindow::startShuttle(int direction)
{
    if (!ensureLoaded()) {
        return;
    }

    if (m_shuttleDirection == 0) {
        m_shuttleHeld.start();
        // Tap jump happens on release if hold was short; start hold seek after delay.
        m_shuttleDirection = direction;
        QTimer::singleShot(200, this, [this, direction]() {
            if (m_shuttleDirection == direction && m_shuttleHeld.isValid()
                && m_shuttleHeld.elapsed() >= 200) {
                if (m_audio->isPlaying()) {
                    m_audio->pause();
                }
                m_shuttleTimer->start();
                setStatus(direction < 0
                              ? QStringLiteral("Seeking reverse.")
                              : QStringLiteral("Seeking forward."));
            }
        });
    }
    m_shuttleDirection = direction;
}

void MainWindow::stopShuttle()
{
    const int direction = m_shuttleDirection;
    const qint64 held = m_shuttleHeld.isValid() ? m_shuttleHeld.elapsed() : 0;
    m_shuttleTimer->stop();
    m_shuttleDirection = 0;

    if (direction != 0 && held < 200) {
        m_audio->skipSeconds(direction * 5.0);
    }
    refreshUi();
}

bool MainWindow::handleAccessibilityKey(QKeyEvent *event)
{
    if (event->key() == Qt::Key_F1
        || (event->key() == Qt::Key_E && !(event->modifiers() & Qt::ShiftModifier)
            && m_mode != AppMode::Source && m_mode != AppMode::Name)) {
        showBriefStatus();
        return true;
    }

    if (event->key() == Qt::Key_F2
        || (event->key() == Qt::Key_E && (event->modifiers() & Qt::ShiftModifier)
            && m_mode != AppMode::Source && m_mode != AppMode::Name)) {
        showDetailedStatus();
        return true;
    }

    return false;
}

QStringList MainWindow::modeHelpLines() const
{
    switch (m_mode) {
    case AppMode::Edit:
        return {
            QStringLiteral("Space play or pause."),
            QStringLiteral("Left and Right seek or hold to shuttle."),
            QStringLiteral("Up and Down change playback volume."),
            QStringLiteral("A sets clip start. D sets clip end."),
            QStringLiteral("Enter previews the clip."),
            QStringLiteral("E shows status. Shift E shows detailed status and help."),
            QStringLiteral("Q quits."),
        };
    case AppMode::Preview:
        return {
            QStringLiteral("Previewing the selected clip."),
            QStringLiteral("Enter continues to naming."),
            QStringLiteral("Right replays."),
            QStringLiteral("Any other key returns to editing."),
            QStringLiteral("E shows status. Shift E shows detailed help."),
            QStringLiteral("Q quits."),
        };
    case AppMode::Source:
        return {
            QStringLiteral("Type the sound source name."),
            QStringLiteral("Enter continues. Left goes back."),
            QStringLiteral("F1 shows status. F2 shows detailed help."),
            QStringLiteral("Q quits."),
        };
    case AppMode::Name:
        return {
            QStringLiteral("Type the sample name."),
            QStringLiteral("Enter continues. Left goes back."),
            QStringLiteral("F1 shows status. F2 shows detailed help."),
            QStringLiteral("Q quits."),
        };
    case AppMode::Final:
        return {
            QStringLiteral("Final confirmation."),
            QStringLiteral("Enter exports the clip."),
            QStringLiteral("Left goes back. Down cancels."),
            QStringLiteral("E shows status. Shift E shows detailed help."),
            QStringLiteral("Q quits."),
        };
    }
    return {};
}

QStringList MainWindow::briefStatusLines() const
{
    QStringList lines {
        QStringLiteral("ClipMark status"),
        QStringLiteral("Mode: %1").arg(QString::fromUtf8(appModeLabel(m_mode))),
        m_transportLabel->text(),
        m_positionLabel->text(),
        m_volumeLabel->text(),
        m_startLabel->text(),
        m_endLabel->text(),
        QStringLiteral("Message: %1").arg(m_statusMessage),
        QStringLiteral("Press Esc to return."),
        QStringLiteral("Press Shift E for detailed status and help."),
    };
    return lines;
}

QStringList MainWindow::detailedStatusLines() const
{
    QStringList lines {
        QStringLiteral("ClipMark detailed status"),
        QStringLiteral("Mode: %1").arg(QString::fromUtf8(appModeLabel(m_mode))),
        m_fileLabel->text(),
        m_transportLabel->text(),
        m_positionLabel->text(),
        m_volumeLabel->text(),
        m_startLabel->text(),
        m_endLabel->text(),
        m_lengthLabel->text(),
    };

    if (m_mode == AppMode::Source || m_mode == AppMode::Name || m_mode == AppMode::Final) {
        lines << QStringLiteral("Source: %1")
                     .arg(m_sourceEdit->text().isEmpty()
                              ? QStringLiteral("blank")
                              : m_sourceEdit->text());
        lines << QStringLiteral("Name: %1")
                     .arg(m_nameEdit->text().isEmpty()
                              ? QStringLiteral("blank")
                              : m_nameEdit->text());
        if (m_mode == AppMode::Final && m_exporter) {
            lines << QStringLiteral("Export file: %1.wav")
                         .arg(m_exporter->buildOutputStem());
        }
    }

    lines << QStringLiteral("Help for this mode:");
    lines << modeHelpLines();
    lines << QStringLiteral("Press Esc to return.");
    lines << QStringLiteral("Press E for brief status.");
    return lines;
}

void MainWindow::showBriefStatus()
{
    refreshUi();
    m_statusDialog->showStatus(QStringLiteral("ClipMark Status"), briefStatusLines());
}

void MainWindow::showDetailedStatus()
{
    refreshUi();
    m_statusDialog->showStatus(
        QStringLiteral("ClipMark Detailed Status"),
        detailedStatusLines());
}

void MainWindow::handleEditKey(QKeyEvent *event)
{
    switch (event->key()) {
    case Qt::Key_Space:
        if (ensureLoaded()) {
            m_audio->togglePlayPause();
        }
        break;
    case Qt::Key_Left:
        startShuttle(-1);
        break;
    case Qt::Key_Right:
        startShuttle(1);
        break;
    case Qt::Key_Up:
        changeVolume(1);
        break;
    case Qt::Key_Down:
        changeVolume(-1);
        break;
    case Qt::Key_A:
        if (ensureLoaded()) {
            m_clip->selectStart();
        }
        break;
    case Qt::Key_D:
        if (ensureLoaded()) {
            m_clip->selectEnd();
        }
        break;
    case Qt::Key_Return:
    case Qt::Key_Enter:
        if (ensureLoaded() && m_clip->beginPreview()) {
            setMode(AppMode::Preview);
        }
        break;
    case Qt::Key_Q:
        close();
        break;
    default:
        break;
    }
}

void MainWindow::handlePreviewKey(QKeyEvent *event)
{
    switch (event->key()) {
    case Qt::Key_Return:
    case Qt::Key_Enter:
        m_clip->stopPreview();
        m_metadata->loadSavedSource();
        m_sourceEdit->setText(m_metadata->soundSource());
        setMode(AppMode::Source);
        setStatus(QStringLiteral("Enter sound source."));
        break;
    case Qt::Key_Right:
        m_clip->replayPreview();
        setStatus(QStringLiteral("Preview replaying."));
        break;
    case Qt::Key_Q:
        close();
        break;
    default:
        m_clip->stopPreview();
        setMode(AppMode::Edit);
        setStatus(QStringLiteral("Adjust start and end, then press Enter to preview."));
        break;
    }
}

void MainWindow::handleSourceKey(QKeyEvent *event)
{
    switch (event->key()) {
    case Qt::Key_Left:
        setMode(AppMode::Preview);
        m_clip->beginPreview();
        break;
    case Qt::Key_Return:
    case Qt::Key_Enter: {
        m_metadata->setSoundSource(m_sourceEdit->text());
        QString error;
        if (!m_metadata->validateSoundSource(&error)) {
            setStatus(error);
            return;
        }
        m_nameEdit->clear();
        setMode(AppMode::Name);
        setStatus(QStringLiteral("Enter the sample name."));
        break;
    }
    case Qt::Key_Q:
        close();
        break;
    default:
        break;
    }
}

void MainWindow::handleNameKey(QKeyEvent *event)
{
    switch (event->key()) {
    case Qt::Key_Left:
        setMode(AppMode::Source);
        break;
    case Qt::Key_Return:
    case Qt::Key_Enter: {
        m_metadata->setSampleName(m_nameEdit->text());
        QString error;
        if (!m_metadata->validateSampleName(&error)) {
            setStatus(error);
            return;
        }
        setMode(AppMode::Final);
        setStatus(QStringLiteral("Final confirmation. Enter exports."));
        break;
    }
    case Qt::Key_Q:
        close();
        break;
    default:
        break;
    }
}

void MainWindow::handleFinalKey(QKeyEvent *event)
{
    switch (event->key()) {
    case Qt::Key_Left:
        setMode(AppMode::Name);
        break;
    case Qt::Key_Down:
        setMode(AppMode::Edit);
        setStatus(QStringLiteral("Export cancelled. Markers and entries retained."));
        break;
    case Qt::Key_Return:
    case Qt::Key_Enter: {
        if (!m_exporter) {
            setStatus(QStringLiteral("No audio loaded."));
            return;
        }
        m_metadata->setSoundSource(m_sourceEdit->text());
        m_metadata->setSampleName(m_nameEdit->text());
        const double exportEnd = m_clip->endSeconds().value_or(0.0);
        QString error;
        const QString path = m_exporter->exportClip(&error);
        if (path.isEmpty()) {
            setStatus(error);
            return;
        }
        m_clip->clearAfterExport();
        m_metadata->clearSampleFields();
        m_nameEdit->clear();
        m_audio->seekSeconds(exportEnd);
        m_audio->play();
        setMode(AppMode::Edit);
        setStatus(QStringLiteral("Exported: %1. Continuing from %2 seconds.")
                      .arg(QFileInfo(path).fileName())
                      .arg(exportEnd, 0, 'f', 1));

        QAccessibleAnnouncementEvent announcement(
            this,
            QStringLiteral("Exported %1").arg(QFileInfo(path).fileName()));
        QAccessible::updateAccessibility(&announcement);
        break;
    }
    case Qt::Key_Q:
        close();
        break;
    default:
        break;
    }
}

bool MainWindow::eventFilter(QObject *watched, QEvent *event)
{
    if (event->type() == QEvent::KeyPress
        && (watched == m_sourceEdit || watched == m_nameEdit)) {
        auto *keyEvent = static_cast<QKeyEvent *>(event);
        if (keyEvent->key() == Qt::Key_F1) {
            showBriefStatus();
            return true;
        }
        if (keyEvent->key() == Qt::Key_F2) {
            showDetailedStatus();
            return true;
        }
        if (keyEvent->key() == Qt::Key_Return
            || keyEvent->key() == Qt::Key_Enter
            || keyEvent->key() == Qt::Key_Left
            || keyEvent->key() == Qt::Key_Q) {
            keyPressEvent(keyEvent);
            return true;
        }
    }
    return QMainWindow::eventFilter(watched, event);
}

void MainWindow::keyPressEvent(QKeyEvent *event)
{
    if (event->isAutoRepeat()
        && event->key() != Qt::Key_Left
        && event->key() != Qt::Key_Right) {
        return;
    }

    if (m_statusDialog->isVisible()) {
        if (event->key() == Qt::Key_E
            && (event->modifiers() & Qt::ShiftModifier)) {
            showDetailedStatus();
            return;
        }
        if (event->key() == Qt::Key_E || event->key() == Qt::Key_F1) {
            showBriefStatus();
            return;
        }
        if (event->key() == Qt::Key_F2) {
            showDetailedStatus();
            return;
        }
    }

    if (handleAccessibilityKey(event)) {
        return;
    }

    // Let line edits handle typing in source/name modes.
    if ((m_mode == AppMode::Source && m_sourceEdit->hasFocus())
        || (m_mode == AppMode::Name && m_nameEdit->hasFocus())) {
        if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter
            || event->key() == Qt::Key_Left || event->key() == Qt::Key_Q
            || event->key() == Qt::Key_F1 || event->key() == Qt::Key_F2) {
            // fall through to mode handlers below for navigation keys
        } else {
            QMainWindow::keyPressEvent(event);
            return;
        }
    }

    switch (m_mode) {
    case AppMode::Edit:
        handleEditKey(event);
        break;
    case AppMode::Preview:
        handlePreviewKey(event);
        break;
    case AppMode::Source:
        handleSourceKey(event);
        break;
    case AppMode::Name:
        handleNameKey(event);
        break;
    case AppMode::Final:
        handleFinalKey(event);
        break;
    }

    refreshUi();
}

void MainWindow::keyReleaseEvent(QKeyEvent *event)
{
    if (event->isAutoRepeat()) {
        return;
    }

    if (event->key() == Qt::Key_Left || event->key() == Qt::Key_Right) {
        stopShuttle();
    }

    QMainWindow::keyReleaseEvent(event);
}
