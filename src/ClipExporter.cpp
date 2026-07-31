#include "ClipExporter.h"

#include "ClipModel.h"
#include "MetadataStore.h"

#include <QDir>
#include <QFileInfo>
#include <QRegularExpression>

#include <sndfile.h>

#include <vector>

ClipExporter::ClipExporter(QString audioPath,
                           QString exportDirectory,
                           ClipModel *clip,
                           MetadataStore *metadata,
                           QObject *parent)
    : QObject(parent)
    , m_audioPath(std::move(audioPath))
    , m_exportDirectory(std::move(exportDirectory))
    , m_clip(clip)
    , m_metadata(metadata)
{
    QDir().mkpath(m_exportDirectory);
}

QString ClipExporter::sanitizeFilename(const QString &name)
{
    QString cleaned = name.trimmed();
    cleaned.replace(QRegularExpression(QStringLiteral("[^\\w\\- ]+")), QString());
    cleaned.replace(QRegularExpression(QStringLiteral("\\s+")), QStringLiteral("_"));
    return cleaned.isEmpty() ? QStringLiteral("sample") : cleaned;
}

QString ClipExporter::buildOutputStem() const
{
    return sanitizeFilename(m_metadata->soundSource())
        + QLatin1Char('-')
        + sanitizeFilename(m_metadata->sampleName());
}

QString ClipExporter::uniqueOutputPath() const
{
    const QString stem = buildOutputStem();
    QString path = QDir(m_exportDirectory).filePath(stem + QStringLiteral(".wav"));
    int counter = 2;
    while (QFileInfo::exists(path)) {
        path = QDir(m_exportDirectory).filePath(
            QStringLiteral("%1_%2.wav").arg(stem).arg(counter));
        ++counter;
    }
    return path;
}

QString ClipExporter::exportClip(QString *error)
{
    QString validationError;
    if (!m_clip->isValid()) {
        if (error) {
            *error = QStringLiteral("Clip start and end are not valid.");
        }
        return {};
    }
    if (!m_metadata->validate(&validationError)) {
        if (error) {
            *error = validationError;
        }
        return {};
    }

    SF_INFO inInfo {};
    SNDFILE *inFile = sf_open(m_audioPath.toUtf8().constData(), SFM_READ, &inInfo);
    if (!inFile) {
        if (error) {
            *error = QStringLiteral("Could not open source WAV for export.");
        }
        return {};
    }

    const sf_count_t startFrame = static_cast<sf_count_t>(
        *m_clip->startSeconds() * inInfo.samplerate);
    const sf_count_t endFrame = static_cast<sf_count_t>(
        *m_clip->endSeconds() * inInfo.samplerate);
    sf_count_t framesRemaining = endFrame - startFrame;

    const QString outputPath = uniqueOutputPath();
    SF_INFO outInfo = inInfo;
    outInfo.frames = framesRemaining;
    outInfo.format = SF_FORMAT_WAV | (inInfo.format & SF_FORMAT_SUBMASK);

    SNDFILE *outFile = sf_open(outputPath.toUtf8().constData(), SFM_WRITE, &outInfo);
    if (!outFile) {
        sf_close(inFile);
        if (error) {
            *error = QStringLiteral("Could not create exported WAV file.");
        }
        return {};
    }

    sf_seek(inFile, startFrame, SEEK_SET);

    constexpr sf_count_t kBlock = 65536;
    std::vector<float> buffer(static_cast<size_t>(kBlock * inInfo.channels));

    while (framesRemaining > 0) {
        const sf_count_t toRead = qMin(kBlock, framesRemaining);
        const sf_count_t readCount = sf_readf_float(inFile, buffer.data(), toRead);
        if (readCount <= 0) {
            break;
        }
        sf_writef_float(outFile, buffer.data(), readCount);
        framesRemaining -= readCount;
    }

    sf_close(outFile);
    sf_close(inFile);

    m_metadata->saveFileMetadata();
    return outputPath;
}
