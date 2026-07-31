#pragma once

#include <QObject>
#include <QString>

class ClipModel;
class MetadataStore;

class ClipExporter : public QObject
{
    Q_OBJECT

public:
    ClipExporter(QString audioPath,
                 QString exportDirectory,
                 ClipModel *clip,
                 MetadataStore *metadata,
                 QObject *parent = nullptr);

    QString buildOutputStem() const;
    QString exportDirectory() const { return m_exportDirectory; }
    QString exportClip(QString *error = nullptr);

    static QString sanitizeFilename(const QString &name);

private:
    QString uniqueOutputPath() const;

    QString m_audioPath;
    QString m_exportDirectory;
    ClipModel *m_clip = nullptr;
    MetadataStore *m_metadata = nullptr;
};
