#pragma once

#include "AppMode.h"

#include <QMainWindow>
#include <QElapsedTimer>

class AudioEngine;
class ClipExporter;
class ClipModel;
class MetadataStore;
class StatusDialog;

class QLabel;
class QLineEdit;
class QPushButton;
class QTimer;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(const QString &projectRoot, QWidget *parent = nullptr);
    ~MainWindow() override;

protected:
    void keyPressEvent(QKeyEvent *event) override;
    void keyReleaseEvent(QKeyEvent *event) override;
    bool eventFilter(QObject *watched, QEvent *event) override;

private slots:
    void openAudioFile();
    void refreshUi();
    void onTick();
    void showBriefStatus();
    void showDetailedStatus();

private:
    void buildUi();
    void setMode(AppMode mode);
    void setStatus(const QString &message);
    void updateModeWidgets();
    void handleEditKey(QKeyEvent *event);
    void handlePreviewKey(QKeyEvent *event);
    void handleSourceKey(QKeyEvent *event);
    void handleNameKey(QKeyEvent *event);
    void handleFinalKey(QKeyEvent *event);
    bool handleAccessibilityKey(QKeyEvent *event);
    void startShuttle(int direction);
    void stopShuttle();
    void changeVolume(int direction);
    int volumeStep(int currentPercent) const;
    QString formatTime(double seconds) const;
    QStringList briefStatusLines() const;
    QStringList detailedStatusLines() const;
    QStringList modeHelpLines() const;
    bool ensureLoaded();

    QString m_projectRoot;
    AppMode m_mode = AppMode::Edit;

    AudioEngine *m_audio = nullptr;
    ClipModel *m_clip = nullptr;
    MetadataStore *m_metadata = nullptr;
    ClipExporter *m_exporter = nullptr;
    StatusDialog *m_statusDialog = nullptr;

    QLabel *m_titleLabel = nullptr;
    QLabel *m_fileLabel = nullptr;
    QLabel *m_exportLabel = nullptr;
    QLabel *m_transportLabel = nullptr;
    QLabel *m_positionLabel = nullptr;
    QLabel *m_volumeLabel = nullptr;
    QLabel *m_startLabel = nullptr;
    QLabel *m_endLabel = nullptr;
    QLabel *m_lengthLabel = nullptr;
    QLabel *m_modeLabel = nullptr;
    QLabel *m_messageLabel = nullptr;
    QLabel *m_controlsLabel = nullptr;
    QLineEdit *m_sourceEdit = nullptr;
    QLineEdit *m_nameEdit = nullptr;
    QPushButton *m_openButton = nullptr;

    QTimer *m_tickTimer = nullptr;
    QTimer *m_shuttleTimer = nullptr;
    int m_shuttleDirection = 0;
    QElapsedTimer m_shuttleHeld;

    QString m_statusMessage;
};
