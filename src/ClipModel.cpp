#include "ClipModel.h"

#include "AudioEngine.h"

ClipModel::ClipModel(AudioEngine *engine, QObject *parent)
    : QObject(parent)
    , m_engine(engine)
    , m_statusMessage(QStringLiteral("Select a start and end time."))
{
}

void ClipModel::selectStart()
{
    m_start = m_engine->positionSeconds();
    m_statusMessage = QStringLiteral("Start set to %1 seconds.")
                          .arg(*m_start, 0, 'f', 1);
    emit statusMessageChanged(m_statusMessage);
    emit changed();
}

void ClipModel::selectEnd()
{
    m_end = m_engine->positionSeconds();
    m_statusMessage = QStringLiteral("End set to %1 seconds.")
                          .arg(*m_end, 0, 'f', 1);
    emit statusMessageChanged(m_statusMessage);
    emit changed();
}

bool ClipModel::isValid() const
{
    return m_start.has_value()
        && m_end.has_value()
        && *m_end > *m_start;
}

bool ClipModel::beginPreview()
{
    if (!isValid()) {
        m_statusMessage = QStringLiteral(
            "Set a start and end time before previewing.");
        emit statusMessageChanged(m_statusMessage);
        return false;
    }

    m_previewActive = true;
    m_engine->seekSeconds(*m_start);
    m_engine->play();
    m_statusMessage = QStringLiteral("Previewing selected clip.");
    emit statusMessageChanged(m_statusMessage);
    emit changed();
    return true;
}

bool ClipModel::replayPreview()
{
    if (!isValid()) {
        return false;
    }
    return beginPreview();
}

void ClipModel::stopPreview()
{
    if (!m_previewActive) {
        return;
    }
    m_previewActive = false;
    m_engine->pause();
    emit changed();
}

void ClipModel::updatePreview()
{
    if (!m_previewActive || !m_end.has_value()) {
        return;
    }

    if (m_engine->positionSeconds() >= *m_end) {
        m_engine->pause();
        m_engine->seekSeconds(*m_end);
        m_statusMessage = QStringLiteral(
            "Preview finished. Enter to continue, Right to replay.");
        emit statusMessageChanged(m_statusMessage);
    }
}

void ClipModel::clearAfterExport()
{
    stopPreview();
    m_start.reset();
    m_end.reset();
    m_statusMessage = QStringLiteral("Select a start and end time.");
    emit statusMessageChanged(m_statusMessage);
    emit changed();
}
