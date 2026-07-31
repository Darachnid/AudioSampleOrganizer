#pragma once

#include <QObject>
#include <QString>

class MetadataStore : public QObject
{
    Q_OBJECT

public:
    explicit MetadataStore(QString storePath, QObject *parent = nullptr);

    void setAudioPath(const QString &audioPath);
    void loadSavedSource();
    bool saveFileMetadata();

    QString soundSource() const { return m_soundSource; }
    QString sampleName() const { return m_sampleName; }
    void setSoundSource(const QString &value);
    void setSampleName(const QString &value);
    void clearSampleFields();

    bool validateSoundSource(QString *error = nullptr) const;
    bool validateSampleName(QString *error = nullptr) const;
    bool validate(QString *error = nullptr) const;

private:
    QString m_storePath;
    QString m_audioPath;
    QString m_soundSource;
    QString m_sampleName;
};
