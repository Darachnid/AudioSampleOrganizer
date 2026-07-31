#include "AudioEngine.h"

#include <QAudioOutput>
#include <QFileInfo>
#include <QMediaPlayer>

AudioEngine::AudioEngine(QObject *parent)
    : QObject(parent)
    , m_player(std::make_unique<QMediaPlayer>(this))
    , m_audioOutput(std::make_unique<QAudioOutput>(this))
{
    m_player->setAudioOutput(m_audioOutput.get());
    m_audioOutput->setVolume(1.0f);

    connect(m_player.get(), &QMediaPlayer::positionChanged, this, [this](qint64 ms) {
        emit positionChanged(ms / 1000.0);
    });
    connect(m_player.get(), &QMediaPlayer::durationChanged, this, [this](qint64 ms) {
        emit durationChanged(ms / 1000.0);
    });
    connect(m_player.get(), &QMediaPlayer::playbackStateChanged, this,
            [this](QMediaPlayer::PlaybackState state) {
                emit playingChanged(state == QMediaPlayer::PlayingState);
            });
}

AudioEngine::~AudioEngine() = default;

bool AudioEngine::load(const QUrl &url, QString *error)
{
    if (!url.isValid() || !url.isLocalFile()) {
        if (error) {
            *error = QStringLiteral("Choose a local WAV file.");
        }
        return false;
    }

    const QString path = url.toLocalFile();
    if (!path.endsWith(QStringLiteral(".wav"), Qt::CaseInsensitive)) {
        if (error) {
            *error = QStringLiteral("ClipMark currently supports WAV files only.");
        }
        return false;
    }

    m_filePath = path;
    m_player->setSource(url);
    pause();
    emit statusMessage(QStringLiteral("Loaded %1. Playback paused.").arg(fileName()));
    return true;
}

void AudioEngine::play()
{
    m_player->play();
    emit statusMessage(QStringLiteral("Playback started."));
}

void AudioEngine::pause()
{
    m_player->pause();
    emit statusMessage(QStringLiteral("Playback paused."));
}

void AudioEngine::togglePlayPause()
{
    if (isPlaying()) {
        pause();
    } else {
        play();
    }
}

void AudioEngine::seekSeconds(double seconds)
{
    const double duration = durationSeconds();
    const double clamped = qBound(0.0, seconds, duration > 0.0 ? duration : seconds);
    m_player->setPosition(static_cast<qint64>(clamped * 1000.0));
}

void AudioEngine::skipSeconds(double deltaSeconds)
{
    seekSeconds(positionSeconds() + deltaSeconds);
    emit statusMessage(
        deltaSeconds >= 0.0
            ? QStringLiteral("Jumped forward %1 seconds.").arg(deltaSeconds, 0, 'f', 1)
            : QStringLiteral("Jumped back %1 seconds.").arg(-deltaSeconds, 0, 'f', 1));
}

void AudioEngine::setVolumePercent(int percent)
{
    m_volumePercent = qBound(0, percent, 100);
    m_audioOutput->setVolume(static_cast<float>(m_volumePercent) / 100.0f);
    emit statusMessage(QStringLiteral("Volume set to %1%.").arg(m_volumePercent));
}

bool AudioEngine::isPlaying() const
{
    return m_player->playbackState() == QMediaPlayer::PlayingState;
}

double AudioEngine::positionSeconds() const
{
    return m_player->position() / 1000.0;
}

double AudioEngine::durationSeconds() const
{
    return m_player->duration() / 1000.0;
}

int AudioEngine::volumePercent() const
{
    return m_volumePercent;
}

QString AudioEngine::filePath() const
{
    return m_filePath;
}

QString AudioEngine::fileName() const
{
    return QFileInfo(m_filePath).fileName();
}
