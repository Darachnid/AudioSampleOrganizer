#pragma once

#include <QObject>
#include <QUrl>
#include <memory>

class QAudioOutput;
class QMediaPlayer;

class AudioEngine : public QObject
{
    Q_OBJECT

public:
    explicit AudioEngine(QObject *parent = nullptr);
    ~AudioEngine() override;

    bool load(const QUrl &url, QString *error = nullptr);

    void play();
    void pause();
    void togglePlayPause();
    void seekSeconds(double seconds);
    void skipSeconds(double deltaSeconds);
    void setVolumePercent(int percent);

    bool isPlaying() const;
    double positionSeconds() const;
    double durationSeconds() const;
    int volumePercent() const;
    QString filePath() const;
    QString fileName() const;

signals:
    void positionChanged(double seconds);
    void durationChanged(double seconds);
    void playingChanged(bool playing);
    void statusMessage(const QString &message);

private:
    std::unique_ptr<QMediaPlayer> m_player;
    std::unique_ptr<QAudioOutput> m_audioOutput;
    QString m_filePath;
    int m_volumePercent = 100;
};
