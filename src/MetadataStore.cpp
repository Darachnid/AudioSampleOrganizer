#include "MetadataStore.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>

MetadataStore::MetadataStore(QString storePath, QObject *parent)
    : QObject(parent)
    , m_storePath(std::move(storePath))
{
}

void MetadataStore::setAudioPath(const QString &audioPath)
{
    m_audioPath = audioPath;
}

void MetadataStore::setSoundSource(const QString &value)
{
    m_soundSource = value;
}

void MetadataStore::setSampleName(const QString &value)
{
    m_sampleName = value;
}

void MetadataStore::clearSampleFields()
{
    m_sampleName.clear();
}

bool MetadataStore::validateSoundSource(QString *error) const
{
    if (m_soundSource.trimmed().isEmpty()) {
        if (error) {
            *error = QStringLiteral("Sound source cannot be empty.");
        }
        return false;
    }
    return true;
}

bool MetadataStore::validateSampleName(QString *error) const
{
    if (m_sampleName.trimmed().isEmpty()) {
        if (error) {
            *error = QStringLiteral("Sample name cannot be empty.");
        }
        return false;
    }
    return true;
}

bool MetadataStore::validate(QString *error) const
{
    return validateSoundSource(error) && validateSampleName(error);
}

void MetadataStore::loadSavedSource()
{
    if (m_audioPath.isEmpty() || !m_soundSource.trimmed().isEmpty()) {
        return;
    }

    QFile file(m_storePath);
    if (!file.open(QIODevice::ReadOnly)) {
        return;
    }

    const auto doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isObject()) {
        return;
    }

    const QJsonObject root = doc.object();
    const QJsonValue entry = root.value(m_audioPath);
    if (!entry.isObject()) {
        return;
    }

    m_soundSource = entry.toObject().value(QStringLiteral("sound_source")).toString();
}

bool MetadataStore::saveFileMetadata()
{
    QJsonObject root;

    QFile file(m_storePath);
    if (file.open(QIODevice::ReadOnly)) {
        const auto doc = QJsonDocument::fromJson(file.readAll());
        if (doc.isObject()) {
            root = doc.object();
        }
        file.close();
    }

    QJsonObject entry = root.value(m_audioPath).toObject();
    entry.insert(QStringLiteral("sound_source"), m_soundSource.trimmed());
    root.insert(m_audioPath, entry);

    QDir().mkpath(QFileInfo(m_storePath).absolutePath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        return false;
    }

    file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
    return true;
}
