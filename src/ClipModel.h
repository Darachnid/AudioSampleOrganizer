#pragma once

#include <QObject>
#include <optional>

class AudioEngine;

class ClipModel : public QObject
{
    Q_OBJECT

public:
    explicit ClipModel(AudioEngine *engine, QObject *parent = nullptr);

    void selectStart();
    void selectEnd();
    bool beginPreview();
    bool replayPreview();
    void stopPreview();
    void updatePreview();
    void clearAfterExport();
    bool isValid() const;

    std::optional<double> startSeconds() const { return m_start; }
    std::optional<double> endSeconds() const { return m_end; }
    bool previewActive() const { return m_previewActive; }
    QString statusMessage() const { return m_statusMessage; }

signals:
    void changed();
    void statusMessageChanged(const QString &message);

private:
    AudioEngine *m_engine = nullptr;
    std::optional<double> m_start;
    std::optional<double> m_end;
    bool m_previewActive = false;
    QString m_statusMessage;
};
