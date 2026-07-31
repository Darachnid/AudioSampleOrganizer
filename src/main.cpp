#include "MainWindow.h"

#include <QApplication>
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("ClipMark"));
    QApplication::setOrganizationName(QStringLiteral("ClipMark"));
    QApplication::setApplicationVersion(QStringLiteral("0.2.0"));

    // Prefer accessible announcements where the platform supports them.
    qputenv("QT_LINUX_ACCESSIBILITY_ALWAYS_ON", QByteArray("1"));

    QString projectRoot = QDir::currentPath();
    const QFileInfo exeInfo(QCoreApplication::applicationFilePath());
    const QDir exeDir = exeInfo.absoluteDir();
    // When running from build/, use the repository root (parent of build).
    if (exeDir.dirName() == QStringLiteral("build")
        && QFileInfo::exists(exeDir.absoluteFilePath(QStringLiteral("../CMakeLists.txt")))) {
        projectRoot = QDir::cleanPath(exeDir.absoluteFilePath(QStringLiteral("..")));
    } else if (QFileInfo::exists(QDir(projectRoot).filePath(QStringLiteral("CMakeLists.txt")))) {
        // keep cwd
    }

    MainWindow window(projectRoot);
    window.show();

    if (argc > 1) {
        // Optional: path argument could be supported later.
        Q_UNUSED(argv);
    }

    return app.exec();
}
